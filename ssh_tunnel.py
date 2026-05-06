"""
Gestione del tunnel SSH per l'accesso remoto al database.

Avvia un SSHTunnelForwarder che fa da ponte tra una porta locale
e la porta PostgreSQL sul server remoto. Il CatastoDBManager si
connette poi a localhost:porta_locale anziché all'host remoto.
"""

import logging
from typing import Optional

logger = logging.getLogger("CatastoGUI.SSHTunnel")

try:
    from sshtunnel import SSHTunnelForwarder, BaseSSHTunnelForwarderError
    SSH_TUNNEL_AVAILABLE = True
except ImportError:
    SSHTunnelForwarder = None
    BaseSSHTunnelForwarderError = Exception
    SSH_TUNNEL_AVAILABLE = False
    logger.warning(
        "Libreria 'sshtunnel' non trovata. "
        "Installa con: pip install sshtunnel"
    )

_active_tunnel: Optional["SSHTunnelForwarder"] = None


def start_ssh_tunnel(
    ssh_host: str,
    ssh_port: int,
    ssh_user: str,
    remote_db_host: str,
    remote_db_port: int,
    ssh_password: Optional[str] = None,
    ssh_key_path: Optional[str] = None,
) -> Optional[int]:
    """
    Apre il tunnel SSH e restituisce la porta locale allocata.

    Il DB va configurato come host='127.0.0.1', port=<porta_restituita>.
    Ritorna None se il tunnel non può essere aperto.
    """
    global _active_tunnel

    if not SSH_TUNNEL_AVAILABLE:
        logger.error("sshtunnel non disponibile — impossibile aprire il tunnel.")
        return None

    stop_ssh_tunnel()

    try:
        kwargs = {
            "ssh_address_or_host": (ssh_host, int(ssh_port)),
            "ssh_username": ssh_user,
            "remote_bind_address": (remote_db_host, int(remote_db_port)),
            "local_bind_address": ("127.0.0.1", 0),  # porta auto-assegnata dal SO
        }
        if ssh_key_path:
            kwargs["ssh_pkey"] = ssh_key_path
        if ssh_password:
            kwargs["ssh_password"] = ssh_password

        tunnel = SSHTunnelForwarder(**kwargs)
        tunnel.start()
        _active_tunnel = tunnel
        local_port = tunnel.local_bind_port
        logger.info(
            f"Tunnel SSH aperto: 127.0.0.1:{local_port} → "
            f"{remote_db_host}:{remote_db_port} via {ssh_host}:{ssh_port}"
        )
        return local_port

    except BaseSSHTunnelForwarderError as e:
        logger.error(f"Errore apertura tunnel SSH: {e}")
        _active_tunnel = None
        return None
    except Exception as e:
        logger.error(f"Errore imprevisto apertura tunnel SSH: {e}", exc_info=True)
        _active_tunnel = None
        return None


def stop_ssh_tunnel() -> None:
    """Chiude il tunnel SSH attivo, se presente."""
    global _active_tunnel
    if _active_tunnel is not None:
        try:
            if getattr(_active_tunnel, "is_active", False):
                _active_tunnel.stop()
            logger.info("Tunnel SSH chiuso.")
        except Exception as e:
            logger.warning(f"Errore durante la chiusura del tunnel SSH: {e}")
        _active_tunnel = None


def is_tunnel_active() -> bool:
    """True se il tunnel SSH è aperto e attivo."""
    return _active_tunnel is not None and getattr(_active_tunnel, "is_active", False)
