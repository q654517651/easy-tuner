"""
Utility modules for FastAPI backend
"""

from .exceptions import (
    EasyTunerError,
    DatasetError,
    DatasetNotFoundError,
    DatasetCreateError,
    ImageProcessingError,
    ImageNotFoundError,
    ImageFormatError,
    LabelingError,
    AIServiceError,
    TrainingError,
    TrainingConfigError,
    TrainingNotFoundError,
    StorageError,
    ConfigError,
    ValidationError
)

from .logger import get_logger
from .validators import (
    validate_image_file,
    validate_video_file,
    validate_dataset_name,
    validate_resolution,
    validate_learning_rate,
    validate_epochs,
    validate_batch_size,
    validate_file_paths,
    validate_directory
)

__all__ = [
    'EasyTunerError',
    'DatasetError',
    'DatasetNotFoundError',
    'DatasetCreateError',
    'ImageProcessingError',
    'ImageNotFoundError',
    'ImageFormatError',
    'LabelingError',
    'AIServiceError',
    'TrainingError',
    'TrainingConfigError',
    'TrainingNotFoundError',
    'StorageError',
    'ConfigError',
    'ValidationError',
    'get_logger',
    'validate_image_file',
    'validate_video_file',
    'validate_dataset_name',
    'validate_resolution',
    'validate_learning_rate',
    'validate_epochs',
    'validate_batch_size',
    'validate_file_paths',
    'validate_directory'
]