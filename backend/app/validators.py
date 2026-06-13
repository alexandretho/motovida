import re

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
UFS = {"AC","AL","AP","AM","BA","CE","DF","ES","GO","MA","MT","MS","MG","PA",
       "PB","PR","PE","PI","RJ","RN","RS","RO","RR","SC","SP","SE","TO"}


def sanitize(value: str, max_len: int = 5000) -> str:
    """Remove caracteres de controle e limita o tamanho da entrada."""
    if value is None:
        return ""
    value = "".join(ch for ch in str(value) if ch == "\n" or ch >= " ")
    return value.strip()[:max_len]


def clean_cpf(cpf: str) -> str:
    return re.sub(r"\D", "", cpf or "")


def is_valid_cpf(cpf: str) -> bool:
    cpf = clean_cpf(cpf)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for i in (9, 10):
        total = sum(int(cpf[j]) * ((i + 1) - j) for j in range(i))
        digit = (total * 10) % 11
        if digit == 10:
            digit = 0
        if digit != int(cpf[i]):
            return False
    return True


def is_valid_email(email: str) -> bool:
    return bool(EMAIL_RE.match(email or ""))


def is_valid_uf(uf: str) -> bool:
    return (uf or "").upper() in UFS


def format_cpf(cpf: str) -> str:
    cpf = clean_cpf(cpf)
    if len(cpf) != 11:
        return cpf
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}"
