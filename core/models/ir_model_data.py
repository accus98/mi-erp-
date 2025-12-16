from core.orm import Model
from core.fields import Char, Integer
from core.db import Database

class IrModelData(Model):
    _name = 'ir.model.data'
    _description = 'Model Data (XML ID Mapping)'
    
    name = Char(string='XML ID', required=True) # e.g. action_partner_list
    module = Char(string='Module', required=True) # e.g. base
    model = Char(string='Model Name', required=True) # e.g. ir.actions.act_window
    res_id = Integer(string='Record ID', required=True) # e.g. 5
    
    @classmethod
    async def _auto_init(cls, cr):
        await super()._auto_init(cr)
        # Unique Constraint
        # Unique Constraint adaptation for SQLite/Postgres
        index_name = "ir_model_data_module_name_uniq"
        q = f'CREATE UNIQUE INDEX IF NOT EXISTS "{index_name}" ON "ir_model_data" ("module", "name")'
        try:
            await cr.execute(q)
        except Exception as e:
            print(f"Warning: Failed to create index {index_name}: {e}")
            pass
    
    def _xmlid_lookup(self, module, xml_id):
        """
        Returns (model, res_id) or None.
        """
        recs = self.search([
            '&', ('module', '=', module), ('name', '=', xml_id)
        ])
        if recs:
            r = recs[0]
            return (r.model, r.res_id)
        return None

    def _xmlid_to_res_id(self, module, xml_id):
        res = self._xmlid_lookup(module, xml_id)
        return res[1] if res else None
