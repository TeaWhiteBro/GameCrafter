"""Measure planted-foot retraction to match locomotion rate to a retargeted body."""
import math
import statistics


def stance_speed(samples, dt, forward):
    speeds=[]
    for foot in (0,1):
        zs=[frame[foot][2] for frame in samples];low,high=min(zs),max(zs)
        for a,b in zip(samples,samples[1:]):
            p,q=a[foot],b[foot]
            if max(p[2],q[2])<=low+(high-low)*.25:
                speed=-sum((q[i]-p[i])*forward[i] for i in (0,1))/dt
                if speed>1:speeds.append(speed)
    if len(speeds)<6:raise ValueError('Insufficient moving stance samples for locomotion calibration')
    speed=statistics.median(speeds)
    if not math.isfinite(speed) or not 10<speed<2000:raise ValueError('Implausible measured locomotion stride')
    return {'stride_speed_cm_s':speed,'stance_samples':len(speeds),'method':'median forward retraction in lowest foot-height quartile'}


def measure_clip(clip,bones):
    import unreal as u
    options=u.AnimPoseEvaluationOptions();samples=[];length=clip.get_play_length();n=80
    pose=u.AnimPoseExtensions.get_anim_pose_at_time(clip,0,options)
    left=u.AnimPoseExtensions.get_ref_bone_pose(pose,bones['left_thigh'],u.AnimPoseSpaces.WORLD).translation
    right=u.AnimPoseExtensions.get_ref_bone_pose(pose,bones['right_thigh'],u.AnimPoseSpaces.WORLD).translation
    x,y=right.y-left.y,left.x-right.x;norm=math.hypot(x,y)
    if norm<1:raise ValueError('Degenerate anatomical basis for stride calibration')
    forward=(x/norm,y/norm)
    for i in range(n):
        pose=u.AnimPoseExtensions.get_anim_pose_at_time(clip,length*i/n,options)
        root=u.AnimPoseExtensions.get_bone_pose(pose,bones['root'],u.AnimPoseSpaces.WORLD).translation
        frame=[]
        for name in ('left_foot','right_foot'):
            foot=u.AnimPoseExtensions.get_bone_pose(pose,bones[name],u.AnimPoseSpaces.WORLD).translation
            frame.append([foot.x-root.x,foot.y-root.y,foot.z])
        samples.append(frame)
    return {**stance_speed(samples,length/n,forward),'clip':clip.get_path_name(),'duration':length,'forward':forward,'evaluated_frames':n}
