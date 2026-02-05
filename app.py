# -*- coding: utf-8 -*-
"""
PDFexport - Aplicacion principal Flask.
Servicio de conversion de archivos PDF a distintos formatos.
"""

import logging
import atexit
from threading import Thread
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS

import config
import models
from api import routes_files, routes_jobs, routes_convert
from utils import job_manager, file_manager

# Importar servicios para registrar procesadores
from services import pdf_split, pdf_to_txt, pdf_to_docx, pdf_to_images

# Configurar logging
logging.basicConfig(
    level=logging.DEBUG if config.DEBUG else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def crear_app():
    """Factory para crear la aplicacion Flask."""
    app = Flask(__name__, static_folder='static')

    # Configuracion
    app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_LENGTH
    app.config['UPLOAD_FOLDER'] = str(config.UPLOAD_FOLDER)

    # Habilitar CORS para todas las rutas
    CORS(app)

    # Registrar blueprints de la API
    app.register_blueprint(routes_files.bp)
    app.register_blueprint(routes_jobs.bp)
    app.register_blueprint(routes_convert.bp)

    # Ruta para servir index.html desde la raiz
    @app.route('/')
    def index():
        return send_from_directory('.', 'index.html')

    # Ruta para servir config.js desde la raiz
    @app.route('/config.js')
    def config_js():
        return send_from_directory('.', 'config.js', mimetype='application/javascript')

    # Ruta para archivos estaticos adicionales en la raiz
    @app.route('/<path:filename>')
    def archivos_raiz(filename):
        # Si es un archivo HTML, buscarlo en static/
        if filename.endswith('.html'):
            return send_from_directory('static', filename)
        # Si no, intentar desde la raiz
        return send_from_directory('.', filename)

    # Manejador de errores para archivos muy grandes
    @app.errorhandler(413)
    def archivo_muy_grande(error):
        return jsonify({
            'success': False,
            'error': {
                'code': 'FILE_TOO_LARGE',
                'message': f'El archivo excede el limite de {config.MAX_CONTENT_LENGTH / (1024*1024*1024):.1f} GB'
            }
        }), 413

    # Manejador de errores genericos
    @app.errorhandler(500)
    def error_interno(error):
        logger.error(f"Error interno: {error}")
        return jsonify({
            'success': False,
            'error': {
                'code': 'INTERNAL_ERROR',
                'message': 'Error interno del servidor'
            }
        }), 500

    return app


def iniciar_scheduler(app):
    """Inicia el scheduler para tareas periodicas."""
    scheduler = BackgroundScheduler()

    # Tarea de limpieza cada hora
    scheduler.add_job(
        func=file_manager.limpiar_archivos_expirados,
        trigger='interval',
        hours=1,
        id='limpieza_archivos',
        name='Limpieza de archivos expirados'
    )

    scheduler.start()
    logger.info("Scheduler iniciado - limpieza programada cada hora")

    # Registrar detencion al cerrar la app
    atexit.register(lambda: scheduler.shutdown())

    return scheduler


def main():
    """Punto de entrada principal."""
    # Inicializar base de datos
    models.inicializar_db()

    # Crear aplicacion
    app = crear_app()

    # Iniciar worker de trabajos
    job_manager.iniciar_worker()

    # Reencolar trabajos pendientes (por si hubo reinicio)
    job_manager.reencolar_trabajos_pendientes()

    # Iniciar scheduler de limpieza
    iniciar_scheduler(app)

    logger.info(f"Iniciando PDFexport en {config.HOST}:{config.PORT}")
    logger.info(f"Debug: {config.DEBUG}")
    logger.info(f"Retencion de archivos: {config.FILE_RETENTION_HOURS} horas")

    # Ejecutar servidor
    app.run(
        host=config.HOST,
        port=config.PORT,
        debug=config.DEBUG,
        threaded=True
    )


if __name__ == '__main__':
    main()
