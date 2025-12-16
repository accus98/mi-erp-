
def _(text):
    """
    Mark string for translation.
    In a real system, this would look up the code translation dictionary.
    For now, it returns the string as is.
    """
    return text
    
def get_code_translation(env, text, lang):
    """
    Fetch translation for code term.
    """
    if lang == 'en_US' or not lang:
        return text
        
    # Search ir.translation for type='code'
    # Source is text
    trans = env['ir.translation'].search([
        ('type', '=', 'code'),
        ('src', '=', text),
        ('lang', '=', lang),
        ('state', '=', 'translated')
    ], limit=1)
    
    if trans:
        return trans[0].value
    return text
