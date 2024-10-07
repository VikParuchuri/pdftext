from pdftext.settings import settings
import onnxruntime as rt


def get_model(model_path=settings.MODEL_PATH):
    sess = rt.InferenceSession(model_path)
    return sess