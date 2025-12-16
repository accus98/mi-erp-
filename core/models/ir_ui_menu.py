from core.orm import Model
from core.fields import Char, Integer, Many2one

class IrUiMenu(Model):
    _name = 'ir.ui.menu'
    _description = 'UI Menus'

    name = Char(string='Menu Name', required=True)
    parent_id = Many2one('ir.ui.menu', string='Parent Menu')
    action_id = Many2one('ir.actions.act_window', string='Action')
    sequence = Integer(string='Sequence')

    async def load_menus(self, user_id=None):
        """
        Returns the full menu tree.
        """
        # Fetch all menus
        menus = await self.search([])
        print(f"DEBUG: load_menus found {len(menus)} raw menus. User={self.env.uid}", flush=True)
        
        if not menus:
            return []

        # Read fields for all menus at once (efficient)
        menu_data = await menus.read(['name', 'parent_id', 'action_id', 'sequence'])
        
        all_menus = []
        for m in menu_data:
            # Resolving Many2one tuple (id, name)
            # read() returns tuple (id, name) or False for m2o
            pid = m['parent_id'][0] if m['parent_id'] else False
            aid = m['action_id'][0] if m['action_id'] else False
            
            all_menus.append({
                'id': m['id'],
                'name': m['name'],
                'parent_id': pid,
                'action_id': aid,
                'sequence': m['sequence'] or 0
            })
            
        # Build Tree
        # 1. Map ID -> structure
        menu_map = {
            m['id']: {
                'id': m['id'], 
                'name': m['name'], 
                'action': m['action_id'], # Keep as ID for frontend
                'children': []
            } 
            for m in all_menus
        }
        
        roots = []
        # sort by sequence? Python list is stable, if search returned ordered ok.
        # But search([]) not guaranteed order unless model _order set.
        # Let's sort manually by sequence
        all_menus.sort(key=lambda x: x['sequence'])

        for m in all_menus:
            pid = m['parent_id']
            if pid and pid in menu_map:
                menu_map[pid]['children'].append(menu_map[m['id']])
            else:
                roots.append(menu_map[m['id']])
                
        return roots
