"""
CP-09 por HTTP: envía varias solicitudes de voto AL MISMO TIEMPO contra el
servidor en ejecución, con la sesión de un mismo usuario, a votaciones de la
misma categoría. Resultado esperado: solo una solicitud registra el voto.

Uso (con el servidor corriendo en otra terminal: python manage.py runserver):

    python scripts/prueba_concurrencia_http.py --email votante@ejemplo.com \
        --intento 2:3 --intento 3:6 --intento 2:4 --intento 3:7

Cada --intento es VOTACION_ID:OPCION_ID (los ids se ven en /api/categorias/).
La contraseña se pide por teclado (o variable DEMO_PASSWORD); no se guarda.
Solo usa la librería estándar de Python.
"""
import argparse
import getpass
import http.cookiejar
import os
import re
import threading
import urllib.parse
import urllib.request


class SinRedireccion(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def abrir_sesion(base, email, clave):
    cookies = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))
    html = opener.open(f"{base}/cuentas/ingresar/").read().decode()
    token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html).group(1)
    datos = urllib.parse.urlencode({"csrfmiddlewaretoken": token, "username": email, "password": clave}).encode()
    respuesta = opener.open(f"{base}/cuentas/ingresar/", datos).read().decode()
    if "Cerrar sesión" not in respuesta:
        raise SystemExit("No se pudo iniciar sesión: revise correo y contraseña.")
    csrf = next(c.value for c in cookies if c.name == "csrftoken")
    return cookies, csrf


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", default="http://127.0.0.1:8000")
    p.add_argument("--email", required=True)
    p.add_argument("--intento", action="append", required=True, help="VOTACION_ID:OPCION_ID")
    a = p.parse_args()
    clave = os.environ.get("DEMO_PASSWORD") or getpass.getpass("Contraseña: ")

    cookies, csrf = abrir_sesion(a.url, a.email, clave)
    barrera = threading.Barrier(len(a.intento))
    resultados = [None] * len(a.intento)

    def enviar(i, intento):
        votacion, opcion = intento.split(":")
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies), SinRedireccion)
        datos = urllib.parse.urlencode({"csrfmiddlewaretoken": csrf, "opcion": opcion}).encode()
        req = urllib.request.Request(f"{a.url}/votaciones/{votacion}/confirmar/", datos,
                                     headers={"Referer": f"{a.url}/votaciones/{votacion}/"})
        barrera.wait()  # todas las solicitudes salen al mismo tiempo
        try:
            opener.open(req)
            resultados[i] = (intento, "?", "sin redirección")
        except urllib.error.HTTPError as e:
            destino = e.headers.get("Location", "")
            estado = "VOTO REGISTRADO" if "mis-votos" in destino else "RECHAZADO"
            resultados[i] = (intento, e.code, estado)

    hilos = [threading.Thread(target=enviar, args=(i, x)) for i, x in enumerate(a.intento)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()

    print(f"\n{'#':>2}  {'votación:opción':<16} {'HTTP':<5} resultado")
    for i, (intento, codigo, estado) in enumerate(resultados, 1):
        print(f"{i:>2}  {intento:<16} {codigo!s:<5} {estado}")
    aceptados = sum(1 for r in resultados if r[2] == "VOTO REGISTRADO")
    print(f"\nSolicitudes simultáneas: {len(resultados)} · registradas: {aceptados} · rechazadas: {len(resultados) - aceptados}")


if __name__ == "__main__":
    main()
