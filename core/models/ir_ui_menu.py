from core.orm import Model
from core.fields import Char, Integer, Many2one

class IrUiMenu(Model):
    _name = 'ir.ui.menu'
    _description = 'UI Menus'

    name = Char(string='Menu Name', required=True)
    parent_id = Many2one('ir.ui.menu', string='Parent Menu')
    action_id = Many2one('ir.actions.act_window', string='Action')
    sequence = Integer(string='Sequence')

    def load_menus(self, user_id=None):
        """
        Returns the full menu tree.
        """
        # Fetch all menus ordered by sequence
        # We need generic search with order, currently search doesn't support order, assume sequence later?
        # Standard ORM approach: fetch all, build tree in python.
        
        menus = self.search([])
        # Need to read content.
        # ORM read? We don't have read() yet, we have access via record attributes.
        
        all_menus = []
        for m in menus:
            all_menus.append({
                'id': m.id,
                'name': m.name,
                'parent_id': m.parent_id.id if m.parent_id else False,
                'action_id': m.action_id.id if m.action_id else False,
                'nm': m.action_id.name if m.action_id else False, # debug
                'sequence': m.sequence or 0
            })
            
        # Build Tree
        # 1. Map ID -> structure
        menu_map = {m['id']: {'id': m['id'], 'name': m['name'], 'action': m['action_id'], 'children': []} for m in all_menus}
        
        roots = []
        for m in all_menus:
            pid = m['parent_id']
            if pid and pid in menu_map:
                menu_map[pid]['children'].append(menu_map[m['id']])
            else:
                roots.append(menu_map[m['id']])
                
        return roots
