from core.orm import Model
from core.fields import Char, Many2many

class ResGroups(Model):
    _name = 'res.groups'
    _description = 'Access Groups'

    name = Char(string='Name', required=True)
    users = Many2many('res.users', string='Users')
    implied_ids = Many2many('res.groups', relation='res_groups_implied_rel', column1='gid', column2='hid', string='Inherits')
    
    # helper for inheritance
    def get_application_groups(self, domain=None):
        return self.search(domain or [])

    async def create(self, vals):
        from core.security import AccessCache
        res = await super().create(vals)
        await AccessCache.invalidate()
        return res

    async def write(self, vals):
        from core.security import AccessCache
        res = await super().write(vals)
        await AccessCache.invalidate()
        return res

    async def unlink(self):
        from core.security import AccessCache
        res = await super().unlink()
        await AccessCache.invalidate()
        return res
