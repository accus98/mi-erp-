import base64
from core.http import route, Response

@route('/web/content/<string:model>/<int:id>/<string:field>', auth='user')
def download_content(req, env):
    """
    Download binary content from a specific field of a record.
    """
    params = req.params
    model_name = params.get('model')
    res_id = int(params.get('id'))
    field_name = params.get('field')
    
    try:
        # Check permissions via browse/read
        record = env[model_name].browse([res_id])
        
        # Read field
        # getattr triggers __get__ which fetches from attachment or cache
        b64_data = getattr(record, field_name)
        
        if not b64_data:
            return Response("No Content", status=404)
        
        # Decode
        file_content = base64.b64decode(b64_data)
        
        # Determine Filename/Mime
        # Try to find the attachment to get strict mimetype?
        # Or guess?
        # IrBinary or logic usually gets filename.
        # For now, generic.
        
        filename = f"{model_name}_{res_id}_{field_name}.bin"
        # If it's an image, browser might sniff it, but correct Content-Type is better.
        # Check if we can find the attachment to get mimetype.
        atts = env['ir.attachment'].search([
            ('res_model', '=', model_name),
            ('res_id', '=', res_id),
            ('name', '=', field_name)
        ])
        
        mime = 'application/octet-stream'
        if atts:
             if atts[0].mimetype:
                 mime = atts[0].mimetype
             # Also assume attachment name is original filename if cleaner
             # But our Binary field implementation used field name as attachment name. 
             # We might need to improve Binary field to store filename in another field.
        
        headers = {
            'Content-Disposition': f'inline; filename="{filename}"'
        }
        
        return Response(file_content, content_type=mime, headers=headers)
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response(f"Error: {e}", status=500)
