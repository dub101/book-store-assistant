Asistente de Libreria
=====================

Como usar
---------

1. Haga doble clic en "BookStoreAssistant.exe" (o en el acceso directo
   del escritorio).
2. Pulse "Examinar..." y seleccione el archivo .csv o .xlsx con los
   ISBNs a procesar.
3. Pulse "Procesar" y espere a que termine. La barra de progreso
   mostrara el avance.
4. Al terminar aparecera un mensaje con el numero de libros listos
   para subir y los que necesitan revision.

Donde encontrar los resultados
------------------------------

Los archivos generados se guardan en la misma carpeta que el archivo
de entrada:

  <nombre_archivo>_upload.xlsx    -> listo para subir al sistema
  <nombre_archivo>_review.xlsx    -> libros que necesitan revision manual
  <nombre_archivo>_handoff.jsonl  -> detalle tecnico (no es necesario abrir)

Tambien puede usar las carpetas "data/input" y "data/output" dentro
de la carpeta de instalacion si prefiere tenerlo todo en un mismo lugar.

Si un archivo ya existe
-----------------------

Si ya procesaste el archivo antes, el programa preguntara si desea
sobrescribir los resultados anteriores. Pulse "Si" para continuar o
"No" para cancelar y conservar los archivos actuales.

Problemas frecuentes
--------------------

- "El archivo no existe": verifique la ruta o seleccione el archivo
  de nuevo con el boton "Examinar...".
- Ventana "Windows protegio su PC": pulse "Mas informacion" y luego
  "Ejecutar de todos modos" (solo la primera vez).
- Si el proceso falla con un error de red, vuelva a intentarlo tras
  unos segundos; algunos servicios limitan peticiones por minuto.

Soporte
-------

Ante cualquier duda, contacte con el administrador que instalo la
aplicacion. No modifique el archivo "bsa.toml" a menos que se lo
pidan expresamente: contiene claves de acceso necesarias para el
funcionamiento del programa.
