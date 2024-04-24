import joblib
from pdftext.settings import settings


def get_model(model_path=settings.MODEL_PATH):
    model = joblib.load(model_path)
    return model