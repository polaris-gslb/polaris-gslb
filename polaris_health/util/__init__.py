# -*- coding: utf-8 -*-


def instance_to_dict(obj):
    """Recursively convert a class instance into a dict
    
    args:
        obj: a class instance

    returns:
        dict representation

    """
    if isinstance(obj, (int, float, complex, bool, str)):
        return obj

    if isinstance(obj, dict):
        new = {}
        for k in obj:
            new[k] = instance_to_dict(obj[k])        
        return new

    if isinstance(obj, (list, tuple)):
        new = []
        for val in obj:
            new.append(instance_to_dict(val))
        return new     
    
    new = {}
    try:
        for k in obj.__dict__:
            new[k] = instance_to_dict(obj.__dict__[k])
    except AttributeError:
        return str(obj)
    else:
        return new

