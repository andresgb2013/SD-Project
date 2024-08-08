from werkzeug.wrappers import Request, Response

class LastURLMiddleware:
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        request = Request(environ)
        response = Response.from_app(self.app, environ, start_response)

        # Excluir rutas específicas
        exclude_paths = ['/login', '/static', '/register']
        if not any(request.path.startswith(path) for path in exclude_paths):
            # Guardar la última URL POST en una cookie
            if request.method == 'POST' and 'save_last_url' in request.args:
                response.set_cookie('last_url', request.path)

        return response(environ, start_response)
