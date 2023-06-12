GSM7_Table = [
    "000A", "000C", "000D", "0020", "0021", "0022", "0023", "0024", "0025", "0026", "0027", "0028",
    "0029", "002A", "002B", "002C", "002D", "002E", "002F", "0030", "0031", "0032", "0033", "0034", "0035", "0036",
    "0037", "0038", "0039", "003A", "003A", "003B", "003C", "003D", "003E", "003F", "0040", "0041", "0042", "0043",
    "0044", "0045", "0046", "0047", "0048", "0049", "004A", "004B", "004C", "004D", "004E", "004F", "0050", "0051",
    "0052", "0053", "0054", "0055", "0056", "0057", "0058", "0059", "005A", "005B", "005C", "005D", "005E", "005F",
    "0061", "0062", "0063", "0064", "0065", "0066", "0067", "0068", "0069", "006A", "006B", "006C", "006D", "006E",
    "006F", "0070", "0071", "0072", "0073", "0074", "0075", "0076", "0077", "0078", "0079", "007A", "007B", "007C",
    "007D", "007E", "00A0", "00A1", "00A3", "00A4", "00A5", "00A7", "00BF", "00C4", "00C5", "00C6", "00C7", "00C9",
    "00D1", "00D6", "00D8", "00DC", "00DF", "00E0", "00E4", "00E5", "00E6", "00E8", "00E9", "00EC", "00F1", "00F2",
    "00F6", "00F8", "00F9", "00FC", "0393", "0394", "0398", "039B", "039E", "03A0", "03A3", "03A6", "03A8", "03A9",
    "20AC"
]

GSM7_Table_Extend = ["007B", "007D", "005B", "005D", "007E", "005C", "005E", "20AC", "007C"]


def hex2char(hex_value):
    result = ''
    n = int(hex_value, 16)
    if n <= 0xFFFF:
        result += chr(n)
    elif n <= 0x10FFFF:
        n -= 0x10000
        result += chr(0xD800 | (n >> 10)) + chr(0xDC00 | (n & 0x3FF))
    return result


def dec2hex(text_string):
    return hex(int(text_string))[2:].upper()


def get_encode_type(str_message):
    encode_type = "GSM7_default"
    gsm7_extend_char_len = 0

    if not str_message:
        return {"encodeType": encode_type, "extendLen": gsm7_extend_char_len}

    for char in str_message:
        char_code = format(ord(char), "04X")
        if char_code in GSM7_Table_Extend:
            gsm7_extend_char_len += 1
        if char_code not in GSM7_Table:
            encode_type = "UNICODE"
            gsm7_extend_char_len = 0
            break

    return {"encodeType": encode_type, "extendLen": gsm7_extend_char_len}

def encode_message(text_string):
    haut = 0
    result = ''

    if not text_string:
        return result

    for char in text_string:
        b = ord(char)
        if haut != 0:
            if 0xDC00 <= b <= 0xDFFF:
                result += dec2hex(0x10000 + ((haut - 0xD800) << 10) + (b - 0xDC00))
                haut = 0
                continue
            else:
                haut = 0

        if 0xD800 <= b <= 0xDBFF:
            haut = b
        else:
            cp = dec2hex(b)
            cp = cp.zfill(4)
            result += cp

    return result


specialChars = ['000D', '000A', '0009', '0000']
specialCharsIgnoreWrap = ['0009', '0000']


def decode_message(string, ignore_wrap):
    if not string:
        return ""

    specials = specialCharsIgnoreWrap if ignore_wrap else specialChars

    def replace(match):
        parens = match.group(1)
        if parens not in specials:
            return hex2char(parens)
        else:
            return ''

    import re
    return re.sub(r'([A-Fa-f0-9]{1,4})', replace, string)


def left_insert(value, length, placeholder):
    value_str = str(value)
    len_value = len(value_str)
    while len_value < length:
        value_str = placeholder + value_str
        len_value += 1
    return value_str

def parse_time(date):
    if "+" in date:
        date = date[:date.rfind("+")]

    if "," in date:
        date_arr = date.split(",")
    else:
        date_arr = date.split(";")

    if len(date_arr) == 0:
        return ""
    else:

        if len(date_arr[0]) == 2:
            date_arr[0] = '20' + date_arr[0]

        time = (
                date_arr[0] + "-" +
                date_arr[1] + "-" +
                date_arr[2] + " " +
                left_insert(date_arr[3], 2, '0') + ":" +
                left_insert(date_arr[4], 2, '0') + ":" +
                left_insert(date_arr[5], 2, '0')
        )
        return time