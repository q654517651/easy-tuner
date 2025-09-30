"""
Labeling core module for FastAPI backend
"""

from .service import LabelingService, get_labeling_service
from .ai_client import AIClient, ModelType

__all__ = [
    'LabelingService',
    'get_labeling_service',
    'AIClient',
    'ModelType'
]