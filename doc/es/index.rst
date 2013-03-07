===============================
Recepción de correo electrónico
===============================

Get Mail es un módulo que le permite la recepción de correos electrónicos en su
ERP. No es un módulo de gestión de correo electrónico como Evolution o
Thunderbird. Este módulo está diseñado más bien para la recepción de correos
electrónicos de cuentas generales (info, ventas, soporte,...) y estos correos
generan registros en su ERP, por ejemplo, casos de CRM.

Configuración
-------------

Para configurar Get Mail deberá configurar las cuentas de correo electrónico en
|menu_getmail_server|\ :

.. |menu_getmail_server| tryref:: getmail.menu_getmail_server_form/complete_name

* Introduzca los datos del servidor de correo IMAP. 
* Especifique el directorio o buzón de su cuenta IMAP de la que desea descargar
  los correos
* Apruebe la cuenta para que esté disponible (opcional)

Paralelamente, se debe crear un modelo de Tryton para que registre el correo.
Este modelo debe contener el método **getmail** para crear el registro del
correo electrónico en el ERP. Los modelos de los módulos CRM contienen este
método por defecto.

.. note:: Get Mail sólo realiza la descarga de correos pendientes de lectura
          (UNSEEN) que estén disponibles en el buzón en el momento de la
          descarga.

Descarga de los correos electrónicos
------------------------------------

Puede descargar los correos electrónicos:

* Manualmente. Cuando una cuenta de Get Mail esté aprobada, podrá descargar el
  correo mediante el botón *Descargar correos*.
* Automáticamente. En |menu_cron_form| configure el cron ''Get Mail'' cada cuanto se acciona. Este cron descarga el correo de todas las cuentas Get Mail que tuviera aprobadas.

.. |menu_cron_form| tryref:: ir.menu_cron_form/complete_name

.. warning:: Recuerde que al configurar el usuario **Cron Get Mail** debe
             añadir los grupos de usuario con permisos de escritura sobre el
             modelo sobre el que se haga la descarga. Por ejemplo si se quiere
             añadir correo en *CRM Project*, el usuario debe tener permisos
             de escritura en el modelo *crm.project*.
