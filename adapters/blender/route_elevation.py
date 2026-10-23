"""Shape-preserving elevation along horizontal control-point distance."""
import math

def interpolate(controls,index,t):
    distances=[max(.001,math.hypot(b[0]-a[0],b[1]-a[1])) for a,b in zip(controls,controls[1:])]
    slopes=[(b[2]-a[2])/h for a,b,h in zip(controls,controls[1:],distances)]
    def tangent(k):
        if k==0:return slopes[0]
        if k==len(controls)-1:return slopes[-1]
        left,right=slopes[k-1],slopes[k]
        if left*right<=0:return 0.
        w1=2*distances[k]+distances[k-1];w2=distances[k]+2*distances[k-1]
        return (w1+w2)/(w1/left+w2/right)
    a,b=controls[index][2],controls[index+1][2];h=distances[index]
    return (2*t**3-3*t*t+1)*a+(t**3-2*t*t+t)*h*tangent(index)+(-2*t**3+3*t*t)*b+(t**3-t*t)*h*tangent(index+1)
