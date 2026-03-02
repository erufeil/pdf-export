He instalado un programa que funciona con tesseract y tika:

programa: nlm-ingestor
IP: 172.21.0.19
PORT: 5001
github: https://github.com/nlmatics/nlm-ingestor

Contenedor levantado con docker-compose:

 pdfacsv:
    image: ghcr.io/nlmatics/nlm-ingestor:latest
    container_name: pdfacsv
    ports:
      - "9020:5001"  # Puerto para la API REST
    networks:
      front-net:
        ipv4_address: 172.21.0.19  
    environment:
      - TIKA_ENDPOINT=http://172.21.0.17:9998  # Apunta a tu contenedor Tika
      - OCR_ENGINE=tesseract  # Usa Tesseract (ya disponible en Tika)
    volumes:
      # Para persistir caché y mejorar rendimiento
      - /mnt/hdd-erf/config/tesseract-pdfacsv/nlm-ingestor/cache:/root/.cache/nlm
    deploy:
      resources:
        limits:
          memory: 1G  # Ajusta según necesites
    depends_on:
      tika-ocr:
        condition: service_healthy  # Espera a que Tika esté saludable
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5001/health"]
      interval: 30s
      timeout: 10s
      retries: 3
---
ya tiene asignada una red y puertos abiertos
responde: 
"Service is running"


---
Para integrarlo

En requirements agregar:
pip install llmsherpa


En Python agregar lo siguiente
"""
Script para invocar nlm-ingestor desde tu aplicación Python
Usando la biblioteca llmsherpa (recomendado)
"""

import os
import pandas as pd
from llmsherpa.readers import LayoutPDFReader
from pathlib import Path

# Configuración - ¡USA LA IP DEL CONTENEDOR nlm-ingestor!
# En tu docker-compose, nlm-ingestor tiene IP 172.17.0.3 y puerto 8080
NLM_INGESTOR_URL = "http://172.17.0.3:8080/api/parseDocument?renderFormat=all"

class PDFTableExtractor:
    def __init__(self, service_url=NLM_INGESTOR_URL):
        """Inicializa el cliente llmsherpa"""
        self.reader = LayoutPDFReader(service_url)
    
    def extract_tables_from_pdf(self, pdf_path, output_dir="./csv_output"):
        """
        Extrae tablas de un PDF y las guarda como CSV
        
        Args:
            pdf_path: Ruta al archivo PDF (dentro del contenedor)
            output_dir: Directorio donde guardar los CSV
        """
        print(f"Procesando: {pdf_path}")
        
        # Crear directorio de salida si no existe
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # Leer el PDF usando llmsherpa (que llama a nlm-ingestor)
        doc = self.reader.read_pdf(str(pdf_path))
        
        # Extraer tablas
        tables_found = 0
        for idx, table in enumerate(doc.tables()):
            # Convertir a DataFrame
            df = table.to_pandas()
            
            # Guardar como CSV
            output_file = Path(output_dir) / f"{Path(pdf_path).stem}_table_{idx+1}.csv"
            df.to_csv(output_file, index=False)
            print(f"  → Tabla {idx+1} guardada: {output_file}")
            tables_found += 1
        
        if tables_found == 0:
            print("  ⚠️ No se encontraron tablas en el documento")
        
        return doc
    
    def extract_tables_to_dataframes(self, pdf_path):
        """
        Extrae tablas y las devuelve como lista de DataFrames
        Útil para integrar directamente con tu aplicación
        """
        doc = self.reader.read_pdf(str(pdf_path))
        
        dataframes = []
        for table in doc.tables():
            dataframes.append(table.to_pandas())
        
        return dataframes, doc

# Ejemplo de uso en tu aplicación Flask/FastAPI/whatever
def procesar_pdf_desde_api(pdf_file_path):
    """
    Función que puedes llamar desde tu API existente
    """
    extractor = PDFTableExtractor()
    
    # Extraer tablas y obtener DataFrames
    dataframes, doc = extractor.extract_tables_to_dataframes(pdf_file_path)
    
    # Ahora puedes hacer lo que necesites con los DataFrames
    resultados = []
    for i, df in enumerate(dataframes):
        # Ejemplo: convertir a diccionario para JSON
        resultados.append({
            "tabla_id": i+1,
            "columnas": df.columns.tolist(),
            "filas": len(df),
            "datos_preview": df.head(3).to_dict(orient='records')
        })
    
    return {
        "exito": True,
        "num_tablas": len(dataframes),
        "resultados": resultados
    }

# Si quieres usar el script de forma autónoma
if __name__ == "__main__":
    # Ejemplo: procesar un PDF específico
    extractor = PDFTableExtractor()
    
    # Asumiendo que tienes PDFs en /data/input/
    pdf_files = list(Path("/data/input").glob("*.pdf"))
    
    for pdf_file in pdf_files:
        extractor.extract_tables_from_pdf(pdf_file, "/data/output")