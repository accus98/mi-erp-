from core.orm import Model
from core.fields import Char, Text, Many2one
from jinja2 import Template

class IrActionsReport(Model):
    _name = 'ir.actions.report'
    _description = 'Report Definition'

    name = Char(string='Name', required=True)
    model = Char(string='Model', required=True)
    report_type = Char(string='Report Type', default='qweb-html') # qweb-pdf, qweb-html
    template = Text(string='Template Content (Jinja2)')
    
    def render(self, docids, data=None):
        """
        Render the report for given docids.
        Returns: bytes (PDF) or string (HTML)
        """
        # Fetch records
        docs = self.env[self.model].browse(docids)
        
        # Determine Template
        # For MVP we store template string in DB `template` field.
        # Odoo usually loads QWeb views. 
        # We will use Jinja2 string for simplicity.
        
        if not self.template:
            return "No template defined."
            
        tmpl = Template(self.template)
        
        # Render
        rendered_html = tmpl.render({
            'docs': docs,
            'user': self.env.user,
            'data': data
        })
        
        if self.report_type == 'qweb-html':
            return rendered_html
        elif self.report_type == 'qweb-pdf':
            # Mock PDF generation
            # Real impl needs weasyprint or wkhtmltopdf
            print("PDF Generation Requested (Mocked)")
            return rendered_html.encode('utf-8') # Return bytes
        
        return rendered_html
