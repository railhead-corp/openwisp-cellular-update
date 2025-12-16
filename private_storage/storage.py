from urllib.parse import urljoin

from private_storage.storage.files import PrivateFileSystemStorage

from ..settings import MODEM_API_BASEURL, MODEM_IMAGE_URL_PATH

file_system_private_storage = PrivateFileSystemStorage(
    base_url=urljoin(MODEM_API_BASEURL, MODEM_IMAGE_URL_PATH)
)
