"""Release-relevant geometry findings must be gates, not passive report fields."""
from .core import StageError


def validate(report):
    if not report.get('ok'):
        raise StageError('Scene adapter failed its contract: '+str(report.get('error')))
    if report.get('exploration'):
        route=report.get('whitebox',{}).get('route_clearance',{})
        if route.get('passed') is not True or not route.get('samples') or route.get('obstructions'):
            raise StageError('Built scene route clearance failed: '+str(len(route.get('obstructions',[])))+
                ' obstructions; inspect whitebox.route_clearance before UE import')
    exposure=report.get('whitebox',{}).get('court_exposure')
    if exposure and exposure.get('passed') is not True:
        raise StageError('Actual court surface failed its declared paving or natural-support contract')
    return report
