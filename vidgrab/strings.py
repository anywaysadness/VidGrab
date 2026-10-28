"""Тексты интерфейса и сообщений об ошибках (русский язык)."""

DISCLAIMER = (
    "Скачивайте только тот контент, на который у вас есть право. "
    "Приложение не обходит DRM, платные подписки и авторизацию."
)

WINDOW_TITLE = "VidGrab — скачивание видео"
WINDOW_TITLE_LOADING = "VidGrab — скачивание видео"

LABEL_URL = "Ссылка на видео:"
LABEL_QUALITY = "Качество:"
LABEL_FOLDER = "Папка сохранения:"
LABEL_TITLE = "Название:"
LABEL_DURATION = "Длительность:"

BTN_PASTE = "Вставить"
BTN_CHECK = "Проверить"
BTN_BROWSE = "Обзор…"
BTN_DOWNLOAD = "Скачать"
BTN_CANCEL = "Отмена"
BTN_OPEN_FOLDER = "Открыть папку"

PLACEHOLDER_URL = "https://..."
PLACEHOLDER_TITLE = "—"
PLACEHOLDER_DURATION = "—"
PLACEHOLDER_SPEED = "Скорость: —"
PLACEHOLDER_ETA = "Осталось: —"

STATUS_IDLE = "Вставьте ссылку и нажмите «Проверить»."
STATUS_CHECKING = "Проверяю ссылку…"
STATUS_READY = "Готово к скачиванию."
STATUS_DOWNLOADING = "Скачивание…"
STATUS_PROCESSING = "Обработка (склейка/конвертация)…"
STATUS_CANCELLING = "Отменяю загрузку…"
STATUS_CANCELLED = "Загрузка отменена пользователем."
STATUS_ERROR = "Ошибка."
STATUS_DONE = "Готово: {path}"
STATUS_BUSY = "Пожалуйста, подождите…"
STATUS_CLIPBOARD_EMPTY = "Буфер обмена пуст."

DIALOG_ERROR_TITLE = "Ошибка"
DIALOG_WARNING_TITLE = "Внимание"
DIALOG_INFO_TITLE = "VidGrab"

MSG_EMPTY_URL = "Введите ссылку на видео."
MSG_INVALID_URL = "Ссылка пустая или некорректная. Нужна ссылка вида https://…"
MSG_NEED_CHECK = "Сначала нажмите «Проверить», чтобы получить список качеств."
MSG_NO_QUALITY = "Выберите качество из списка."
MSG_CLOSE_WHILE_DOWNLOADING = "Идёт загрузка. Отменить её и закрыть приложение?"
MSG_CLOSE_WAIT = "Не удалось остановить загрузку. Подождите немного и попробуйте снова."
MSG_NO_METADATA = "Не удалось получить данные о видео. Проверьте ссылку."

ERRORS = {
    "invalid_url": "Ссылка пустая или некорректная. Нужна ссылка вида https://…",
    "network": "Нет подключения к интернету. Проверьте сеть и повторите попытку.",
    "unavailable": (
        "Видео недоступно: приватное, удалённое или требует авторизации. "
        "Приложение не обходит авторизацию и DRM."
    ),
    "permission": "Нет прав на запись в выбранную папку. Выберите другую папку.",
    "ffmpeg": (
        "FFmpeg не найден. Переустановите приложение: папка dist/VidGrab повреждена "
        "или файл ffmpeg.exe удалён."
    ),
    "generic": "Ошибка загрузчика: {detail}",
    "cancelled": "Загрузка отменена пользователем.",
}

# Коды ошибок, которые понимает интерфейс.
ERROR_CODES = ("invalid_url", "network", "unavailable", "permission", "ffmpeg", "generic", "cancelled")
