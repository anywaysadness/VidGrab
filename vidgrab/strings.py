"""Тексты интерфейса и сообщений об ошибках (русский язык)."""

# Одна нейтральная строка вместо юридической лекции: приложение не ограничивает
# пользователя, а лишь напоминает о правах на контент.
DISCLAIMER = "Скачивайте только тот контент, на который у вас есть право."

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
BTN_SETTINGS = "Настройки"
BTN_REPORT = "Отчёт"
BTN_SAVE = "Сохранить"
BTN_DIALOG_CANCEL = "Отмена"

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
STATUS_REPORT_DONE = "Отчёт создан: {path}"

RESULT_FILE = "Файл: {name}"
RESULT_OPEN_FOLDER = "Открыть папку"
RESULT_FOLDER_HINT = "Папка: {folder}"

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
MSG_OPEN_FOLDER_FAILED = "Не удалось открыть папку:\n{path}\n{detail}"
MSG_BOT_CHECK_SETTINGS = (
    "YouTube требует подтверждения. Открыть настройки, чтобы включить cookies браузера?"
)

# Настройки.
SETTINGS_TITLE = "Настройки"
SETTINGS_COOKIES = "Cookies браузера:"
SETTINGS_COOKIES_NONE = "Не использовать"
SETTINGS_COOKIES_FILE = "Файл cookies.txt"
SETTINGS_COOKIES_FILE_LABEL = "Файл cookies.txt:"
SETTINGS_COOKIES_HINT = (
    "Cookies нужны, только если сайт просит войти или подтвердить, что вы не бот. "
    "Они читаются локально и никуда не отправляются."
)
SETTINGS_CLIENT = "Клиент YouTube:"
SETTINGS_CLIENT_AUTO = "Авто"
SETTINGS_COOKIES_FILE_EMPTY = "Выберите файл cookies.txt или укажите другой источник cookies."
SETTINGS_COOKIES_FILE_MISSING = "Файл cookies.txt не найден:\n{path}"

# Отчёт.
REPORT_TITLE = "Отчёт"
REPORT_SAVED = "Отчёт создан:\n{path}\n\nВ нём есть ссылки и пути из лога, но нет cookies. Перед отправкой проверьте содержимое."
REPORT_FAILED = "Не удалось создать отчёт: {detail}"
REPORT_OPEN_FOLDER = "Открыть папку с отчётом"

ERRORS = {
    "invalid_url": "Ссылка пустая или некорректная. Нужна ссылка вида https://…",
    "network": "Нет подключения к интернету. Проверьте сеть и повторите попытку.",
    "unavailable": (
        "Видео недоступно: приватное, удалённое, с ограничением по региону "
        "или требует входа в аккаунт."
    ),
    "bot_check": (
        "YouTube просит подтвердить, что вы не бот. Откройте «Настройки» и включите cookies "
        "браузера (Chrome, Edge или Firefox) либо повторите попытку позже."
    ),
    "cookies": (
        "Не удалось прочитать cookies браузера. Войдите в нужный аккаунт, закройте браузер "
        "и повторите; либо укажите файл cookies.txt в настройках."
    ),
    "forbidden": (
        "Сервер отклонил загрузку файла (HTTP 403). Повторите попытку, выберите другое "
        "качество или включите cookies браузера в настройках."
    ),
    "format_unavailable": (
        "У видео нет потока в выбранном качестве. Выберите другое качество или «best»."
    ),
    "drm": "Видео защищено DRM (например, платный онлайн-кинотеатр). Такие видео не поддерживаются.",
    "permission": "Нет прав на запись в выбранную папку. Выберите другую папку.",
    "ffmpeg": (
        "FFmpeg не найден. Переустановите приложение: папка dist/VidGrab повреждена "
        "или файл ffmpeg.exe удалён."
    ),
    "generic": "Ошибка загрузчика: {detail}",
    "cancelled": "Загрузка отменена пользователем.",
}

# Коды ошибок, которые понимает интерфейс.
ERROR_CODES = (
    "invalid_url",
    "network",
    "unavailable",
    "bot_check",
    "cookies",
    "forbidden",
    "format_unavailable",
    "drm",
    "permission",
    "ffmpeg",
    "generic",
    "cancelled",
)
