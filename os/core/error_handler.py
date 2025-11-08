"""
Centralized Error Handler for KI-ana OS

Provides:
- User-friendly error messages
- Error logging
- Recovery suggestions
- Error categorization
"""
from typing import Dict, Any, Optional
from loguru import logger
import traceback


class ErrorCategory:
    """Error categories"""
    NETWORK = "network"
    HARDWARE = "hardware"
    PERMISSION = "permission"
    NOT_FOUND = "not_found"
    CONFIGURATION = "configuration"
    EXTERNAL_SERVICE = "external_service"
    INTERNAL = "internal"
    USER_INPUT = "user_input"


class KIanaError(Exception):
    """Base exception for KI-ana OS"""
    
    def __init__(
        self,
        message: str,
        category: str = ErrorCategory.INTERNAL,
        user_message: Optional[str] = None,
        recovery_suggestions: Optional[list] = None,
        original_error: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.category = category
        self.user_message = user_message or self._generate_user_message()
        self.recovery_suggestions = recovery_suggestions or []
        self.original_error = original_error
    
    def _generate_user_message(self) -> str:
        """Generate user-friendly message based on category"""
        category_messages = {
            ErrorCategory.NETWORK: "Netzwerkverbindung fehlgeschlagen. Bitte überprüfe deine Internetverbindung.",
            ErrorCategory.HARDWARE: "Hardware-Problem erkannt. Bitte überprüfe deine Geräte.",
            ErrorCategory.PERMISSION: "Keine Berechtigung für diese Aktion. Eventuell sudo/admin-Rechte erforderlich.",
            ErrorCategory.NOT_FOUND: "Die angeforderte Ressource wurde nicht gefunden.",
            ErrorCategory.CONFIGURATION: "Konfigurationsfehler. Bitte überprüfe die Einstellungen.",
            ErrorCategory.EXTERNAL_SERVICE: "Externer Service nicht erreichbar. Versuche es später erneut.",
            ErrorCategory.INTERNAL: "Interner Fehler. Das sollte nicht passieren.",
            ErrorCategory.USER_INPUT: "Ungültige Eingabe. Bitte überprüfe deine Anfrage."
        }
        return category_messages.get(self.category, self.message)


class ErrorHandler:
    """Centralized error handler"""
    
    @staticmethod
    def handle_error(
        error: Exception,
        context: str = "",
        user_facing: bool = True
    ) -> Dict[str, Any]:
        """Handle an error and return user-friendly response
        
        Args:
            error: The exception to handle
            context: Context where error occurred
            user_facing: Whether to include user-friendly messages
            
        Returns:
            Dict with error information
        """
        # Log the full error
        if context:
            logger.error(f"Error in {context}: {error}")
        else:
            logger.error(f"Error: {error}")
        logger.debug(f"Full traceback:\n{traceback.format_exc()}")
        
        # Handle KIanaError specially
        if isinstance(error, KIanaError):
            return {
                "success": False,
                "error": error.user_message if user_facing else str(error),
                "error_category": error.category,
                "recovery_suggestions": error.recovery_suggestions,
                "technical_details": str(error) if user_facing else None
            }
        
        # Categorize and handle common errors
        category, user_msg, suggestions = ErrorHandler._categorize_error(error)
        
        return {
            "success": False,
            "error": user_msg if user_facing else str(error),
            "error_category": category,
            "recovery_suggestions": suggestions,
            "technical_details": str(error) if user_facing else None
        }
    
    @staticmethod
    def _categorize_error(error: Exception) -> tuple:
        """Categorize an error and provide user message and suggestions
        
        Returns:
            (category, user_message, recovery_suggestions)
        """
        error_str = str(error).lower()
        error_type = type(error).__name__
        
        # Network errors
        if any(keyword in error_str for keyword in ["connection", "network", "timeout", "unreachable"]):
            return (
                ErrorCategory.NETWORK,
                "Netzwerkverbindung fehlgeschlagen. Bitte überprüfe deine Internetverbindung.",
                [
                    "Überprüfe deine Internetverbindung",
                    "Versuche es in ein paar Sekunden erneut",
                    "Prüfe deine Firewall-Einstellungen"
                ]
            )
        
        # Permission errors
        if "permission" in error_str or error_type in ["PermissionError", "OSError"]:
            return (
                ErrorCategory.PERMISSION,
                "Keine Berechtigung für diese Aktion. Eventuell sudo/admin-Rechte erforderlich.",
                [
                    "Führe den Befehl mit sudo aus",
                    "Überprüfe Datei-/Ordner-Berechtigungen",
                    "Stelle sicher, dass du die nötigen Rechte hast"
                ]
            )
        
        # File not found errors
        if "not found" in error_str or error_type == "FileNotFoundError":
            return (
                ErrorCategory.NOT_FOUND,
                "Die angeforderte Ressource wurde nicht gefunden.",
                [
                    "Überprüfe, ob die Datei/Ressource existiert",
                    "Prüfe den Pfad",
                    "Stelle sicher, dass alle Abhängigkeiten installiert sind"
                ]
            )
        
        # Import/Module errors
        if error_type in ["ImportError", "ModuleNotFoundError"]:
            module_name = error_str.split("'")[1] if "'" in error_str else "unknown"
            return (
                ErrorCategory.CONFIGURATION,
                f"Modul '{module_name}' nicht gefunden. Bitte installiere die Abhängigkeiten.",
                [
                    f"Installiere mit: pip install {module_name}",
                    "Führe aus: pip install -r requirements.txt",
                    "Überprüfe, ob die virtuelle Umgebung aktiviert ist"
                ]
            )
        
        # Value/Type errors (user input)
        if error_type in ["ValueError", "TypeError", "KeyError"]:
            return (
                ErrorCategory.USER_INPUT,
                "Ungültige Eingabe oder Daten. Bitte überprüfe deine Anfrage.",
                [
                    "Überprüfe deine Eingabe",
                    "Stelle sicher, dass alle Parameter korrekt sind",
                    "Versuche eine andere Formulierung"
                ]
            )
        
        # Default: internal error
        return (
            ErrorCategory.INTERNAL,
            "Ein interner Fehler ist aufgetreten. Das sollte nicht passieren.",
            [
                "Versuche es erneut",
                "Starte die Anwendung neu",
                "Melde diesen Fehler, falls er weiterhin auftritt"
            ]
        )
    
    @staticmethod
    def wrap_async(func):
        """Decorator to wrap async functions with error handling"""
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                return ErrorHandler.handle_error(e, context=func.__name__)
        return wrapper
    
    @staticmethod
    def wrap_sync(func):
        """Decorator to wrap sync functions with error handling"""
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                return ErrorHandler.handle_error(e, context=func.__name__)
        return wrapper


# Convenience decorators
def handle_errors_async(func):
    """Decorator for async error handling"""
    return ErrorHandler.wrap_async(func)


def handle_errors_sync(func):
    """Decorator for sync error handling"""
    return ErrorHandler.wrap_sync(func)


# Helper function for creating user-friendly error responses
def create_error_response(
    message: str,
    category: str = ErrorCategory.INTERNAL,
    suggestions: Optional[list] = None
) -> Dict[str, Any]:
    """Create a standardized error response
    
    Args:
        message: User-friendly error message
        category: Error category
        suggestions: Recovery suggestions
        
    Returns:
        Standardized error dict
    """
    return {
        "success": False,
        "error": message,
        "error_category": category,
        "recovery_suggestions": suggestions or [],
        "response": f"❌ {message}"
    }
