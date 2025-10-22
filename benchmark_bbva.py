#!/usr/bin/env python3
"""
Script para comparar el rendimiento entre Funciones_BBVA.py y Fast_BBVA.py
"""

import time
import sys
import os
from pathlib import Path

# Agregar el directorio padre al path para importar los módulos
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from Scraping_Bancos_MX.Funciones_BBVA import Scrap_Estado as Scrap_Estado_Original
    from Scraping_Bancos_MX.Fast_BBVA import Scrap_Estado as Scrap_Estado_Fast
except ImportError as e:
    print(f"Error al importar módulos: {e}")
    sys.exit(1)

def medir_tiempo(func, archivo_pdf, nombre_funcion):
    """Mide el tiempo de ejecución de una función"""
    print(f"Ejecutando {nombre_funcion}...")
    inicio = time.time()
    try:
        resultado = func(archivo_pdf)
        fin = time.time()
        tiempo_transcurrido = fin - inicio
        print(f"✅ {nombre_funcion} completada en {tiempo_transcurrido:.2f} segundos")
        print(f"   Filas procesadas: {len(resultado) if resultado is not None else 0}")
        return tiempo_transcurrido, resultado
    except Exception as e:
        fin = time.time()
        tiempo_transcurrido = fin - inicio
        print(f"❌ Error en {nombre_funcion} después de {tiempo_transcurrido:.2f} segundos: {e}")
        return tiempo_transcurrido, None

def buscar_pdf_ejemplo():
    """Busca un archivo PDF de ejemplo en el workspace"""
    # Rutas posibles donde pueden estar los PDFs de ejemplo
    rutas_posibles = [
        "AZTECA/*.pdf",
        "proto/data/*.pdf",
        "*.pdf"
    ]
    
    workspace_root = Path(__file__).parent.parent
    
    for ruta in rutas_posibles:
        pdfs = list(workspace_root.glob(ruta))
        if pdfs:
            return str(pdfs[0])
    
    return None

def main():
    print("🚀 Comparación de rendimiento: Funciones_BBVA.py vs Fast_BBVA.py")
    print("=" * 70)
    
    # Buscar archivo PDF de ejemplo
    archivo_pdf = buscar_pdf_ejemplo()
    
    if not archivo_pdf:
        print("❌ No se encontró ningún archivo PDF de ejemplo en el workspace")
        print("   Por favor, especifica la ruta de un archivo PDF:")
        archivo_pdf = input("   Ruta del archivo PDF: ").strip()
        
        if not archivo_pdf or not os.path.exists(archivo_pdf):
            print("❌ Archivo no válido o no existe")
            return
    
    print(f"📄 Archivo de prueba: {os.path.basename(archivo_pdf)}")
    print("-" * 70)
    
    # Medir función original
    tiempo_original, resultado_original = medir_tiempo(
        Scrap_Estado_Original, 
        archivo_pdf, 
        "Funciones_BBVA.Scrap_Estado (Original)"
    )
    
    print("-" * 70)
    
    # Medir función optimizada
    tiempo_fast, resultado_fast = medir_tiempo(
        Scrap_Estado_Fast, 
        archivo_pdf, 
        "Fast_BBVA.Scrap_Estado (Optimizada)"
    )
    
    print("=" * 70)
    print("📊 RESULTADOS DE LA COMPARACIÓN:")
    print(f"   Tiempo original:    {tiempo_original:.2f} segundos")
    print(f"   Tiempo optimizado:  {tiempo_fast:.2f} segundos")
    
    if tiempo_original > 0 and tiempo_fast > 0:
        mejora = ((tiempo_original - tiempo_fast) / tiempo_original) * 100
        factor = tiempo_original / tiempo_fast
        print(f"   Mejora:             {mejora:.1f}% más rápido")
        print(f"   Factor de mejora:   {factor:.1f}x")
        
        if mejora > 0:
            print(f"🎉 ¡La versión optimizada es {mejora:.1f}% más rápida!")
        elif mejora < -5:
            print(f"⚠️  La versión optimizada es {abs(mejora):.1f}% más lenta")
        else:
            print("📊 Rendimiento similar entre ambas versiones")
    
    # Verificar consistencia de resultados
    if resultado_original is not None and resultado_fast is not None:
        if len(resultado_original) == len(resultado_fast):
            print(f"✅ Ambas versiones procesaron la misma cantidad de filas ({len(resultado_original)})")
        else:
            print(f"⚠️  Diferencia en número de filas: Original={len(resultado_original)}, Fast={len(resultado_fast)}")
    
    print("=" * 70)

if __name__ == "__main__":
    main()
