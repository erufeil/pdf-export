# -*- coding: utf-8 -*-
"""
Etapa 48 — Contador de Tokens.
Cuenta palabras, caracteres, bytes y tokens (cl100k_base) de un texto.
cl100k_base es el encoding de GPT-4, GPT-3.5-turbo y aproxima a Claude.
"""
import logging
import tiktoken

logger = logging.getLogger(__name__)

_enc = None


def _get_encoder():
    """Carga el encoder una sola vez (lazy, se cachea en memoria del proceso)."""
    global _enc
    if _enc is None:
        _enc = tiktoken.get_encoding('cl100k_base')
    return _enc


def contar_tokens(texto: str) -> dict:
    """
    Retorna estadísticas del texto: tokens, palabras, caracteres y bytes.
    Lanza RuntimeError si tiktoken no puede cargar el vocabulario.
    """
    try:
        enc = _get_encoder()
        tokens = len(enc.encode(texto))
    except Exception as e:
        logger.error(f"tiktoken error: {e}")
        raise RuntimeError(f"No se pudo calcular tokens: {e}")

    palabras = len(texto.split()) if texto.strip() else 0
    caracteres = len(texto)
    bytes_utf8 = len(texto.encode('utf-8'))

    return {
        'tokens': tokens,
        'palabras': palabras,
        'caracteres': caracteres,
        'bytes': bytes_utf8,
        'encoding': 'cl100k_base',
    }
