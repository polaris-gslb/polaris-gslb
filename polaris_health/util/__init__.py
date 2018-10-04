# -*- coding: utf-8 -*-


def instance_to_dict(obj, ignore_private=False):
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
            new[k] = instance_to_dict(obj[k], ignore_private)        
        return new

    if isinstance(obj, (list, tuple)):
        new = []
        for val in obj:
            new.append(instance_to_dict(val, ignore_private))
        return new     
    
    new = {}
    try:
        for k in obj.__dict__:
            if ignore_private and k.startswith("_"):
                continue
            new[k] = instance_to_dict(obj.__dict__[k], ignore_private)
    except AttributeError:
        return str(obj)
    else:
        return new

