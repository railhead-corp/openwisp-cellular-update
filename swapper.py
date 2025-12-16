import swapper


def get_model_name(model):
    """Get swappable model name"""
    return swapper.get_model_name("modem_upgrader", model)


def load_model(model):
    """Load swappable model"""
    return swapper.load_model("modem_upgrader", model)
