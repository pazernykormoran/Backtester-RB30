def singleton(class_):
    """
    Usage:

    @singleton
    class NameOfClass():
        pass
    """
    instances = {}

    def getinstance(*args, **kwargs):
        if class_ not in instances:
            instances[class_] = class_(*args, **kwargs)
        return instances[class_]

    return getinstance
