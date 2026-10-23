"""Interchangeable arch curves with fixed opening width and overall height."""
import math

def parameters(radius,total_height,profile='round'):
    if profile not in ('round','pointed'):raise ValueError('Unknown arch profile')
    rise=radius if profile=='round' else min(radius*1.27,total_height*.65)
    return total_height-rise,rise

def ordinate(angle,radius,outer_radius,rise,profile='round'):
    if profile=='round':return radius*math.sin(angle)
    x=abs(math.cos(angle))
    return rise*math.sqrt(max(0,1-((x+1)*.5)**2))/(math.sqrt(3)*.5)*radius/outer_radius
