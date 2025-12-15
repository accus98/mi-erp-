import sys
import os

sys.path.append(os.getcwd())

try:
    from addons.base.models.res_users import ResUsers
    from core.orm import Model

    print("ResUsers MRO:", ResUsers.mro())
    print("Has _auto_init?", hasattr(ResUsers, '_auto_init'))
    print("Model has _auto_init?", hasattr(Model, '_auto_init'))
    
except Exception as e:
    import traceback
    traceback.print_exc()
