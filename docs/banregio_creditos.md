# Banregio: detalle de movimientos de créditos (opcional)

El estado de cuenta único de Banregio incluye, además de las cuentas, tablas de
movimientos de los créditos (MiCrédito Fijo, AutoRegio, Hipotecario...).

- `Scrap_Estado_BanRegio(ruta)` **no** las incluye (comportamiento por defecto).
- `Scrap_Creditos_BanRegio(ruta)` las regresa con el esquema estándar
  (`fecha, descripcion, deposito, retiro, saldo`): `deposito` = ABONO al
  crédito, `retiro` = CARGO, `saldo` vacío.
- `Scrap_Estado_BanRegio(ruta, incluir_creditos=True)` las agrega al final de
  los movimientos de la cuenta.

## Por qué es opcional

Los abonos al crédito **no son flujo de la cuenta**. Sumarlos como depósito:

- infla los ingresos (un pago al crédito no es dinero que entre al cliente), y
- duplica los pagos que ya salen como retiro de la cuenta (el pago de la
  mensualidad aparece en la cuenta como retiro y otra vez como abono en el
  crédito).

Úsalo solo cuando se quiera explícitamente el detalle del crédito (por
ejemplo, para comparar contra otra herramienta que sí lo lista, como Afirme).
No lo mezcles con depósitos/retiros de cuenta para calcular ingresos.

## Formatos soportados

- `Detalle de Movimientos` (`DIA CONCEPTO CARGOS ABONOS`), p. ej. MiCrédito Fijo.
- `DETALLE DE LOS ULTIMOS MOVIMIENTOS` (`FECHA AMORTI. REFERENCIA CONCEPTO CARGO ABONO`),
  p. ej. AutoRegio / Hipotecario.

La tabla `REGIOCUENTA REGIOCREDITO` no se lee: repite los movimientos de la
cuenta que ya salen en `Scrap_Estado_BanRegio`.
