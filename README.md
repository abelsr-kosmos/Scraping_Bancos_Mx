# Scraping Datos Bancarios Mx

Esta libreria se hizo con el objetivo de facilitar la extracción de datos de los estados de cuenta de la mayoría de los bancos mexicanos.


# Funcionamiento
Para obtener los datos bancarios, primero tenemos que importar las funciones del banco que necesitamos. Todos los diferentes bancos tienen el mismo nombre para el análisis del estado. Únicamente tendrás que llamar a la función y enviar como parámetro una dirección donde esté el archivo. El proceso nos devolverá un DataFrame de Pandas con los datos extraídos.
Ejemplo:

    from Funciones_BBVA import Scrap_Estado
    
    estado_extraido = Scrap_Estado("ruta/ejemplo/estado.pdf")

La estructura del Dataframe recibidó es la siguiente:

|FECHA|CONCEPTO|ORIGEN|DEPOSITO|RETIRO|SALDO|TIPO MOVIMIENTO|CONTRAPARTE|INSTITUCION CONTRAPARTE| CONCEPTO MOVIMIENTO 
|--|--|--|--|--|--|--|--|--|--|

Definición estructura:
Fecha : dia/mes/año
Concepto : Descripción completa del movimiento
Origen* : Referencia del movimiento
Deposito : Valor del Depósito  
Retiro : Valor del Retiro
Saldo* : Valor del Saldo despues de la operación
Tipo Movimiento : Puede tomar los siguientes valores

 - SPEI
 - PAGO
 - COMPRA
 - COMISION
 - IVACOMISION
 - OTRO
Contraparte* : Es el destinatario o remitente del movimiento
Institucion Contraparte* : Es la institucón Bancaria a la cual pertence la contraparte

Concepto*: Es el concepto de la operación
 
 ** Estos campos pueden existir o no dependiendo el Banco y el tipo de movimiento

# Importante

-   El archivo debe estar digitalizado, ya que el scraping se realiza extrayendo texto.
-   El archivo debe ser un estado de cuenta bancario de la sucursal requerida.
-   El script se elaboró utilizando estados de cuenta hasta la fecha de julio de 2023. Si se desean extraer datos de formatos más recientes o lo suficientemente antiguos como para que haya cambios en el formato, es posible que el script no funcione correctamente.
-   Algunos bancos no están incluidos en la librería. Puedes consultar la lista de bancos para verificar su disponibilidad.
-   Algunos bancos pueden no proporcionar detalles precisos debido a que el scraping se basa en la descripción, y algunos bancos no incluyen descripciones detalladas.
-   Se realizaron múltiples pruebas con diferentes estados de cuenta para cada banco, excepto para Afirme e Inbursa, ya que solo se pudieron probar con un único estado de cuenta.

# Lista de Bancos

 - Afirme
 - BanBajio
 - Banorte
 - BanRegio
 - BBVA
 - HeyBanco
 - Inbursa
 - Santander
 - Scotiabank
