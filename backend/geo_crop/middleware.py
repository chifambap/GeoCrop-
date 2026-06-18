PROTECT_SCRIPT = b"""<script>
document.addEventListener('contextmenu',e=>e.preventDefault());
document.addEventListener('keydown',e=>{
if(e.key==='F12'||(e.ctrlKey&&e.shiftKey&&['I','J','C'].includes(e.key))||(e.ctrlKey&&e.key==='u'))e.preventDefault();
});
document.addEventListener('selectstart',e=>{if(!['INPUT','TEXTAREA','SELECT'].includes(e.target.tagName))e.preventDefault();});
</script>"""


class DisableInspectMiddleware:
    """Inject anti-inspect script into all HTML responses."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        content_type = response.get('Content-Type', '')
        if 'text/html' in content_type and hasattr(response, 'content'):
            content = response.content
            if b'</body>' in content:
                response.content = content.replace(b'</body>', PROTECT_SCRIPT + b'</body>', 1)
                response['Content-Length'] = len(response.content)
        return response
