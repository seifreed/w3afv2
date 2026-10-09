import hashlib


def gen_hash(request):
    """
    Generate an unique ID for a request

    Characters which can't be encoded (lone surrogates) are escaped instead of
    raising errors like:
        * Encoding error #1917
        * https://github.com/andresriancho/w3af/issues/1917
    """
    req = request
    headers_1 = "".join(f"{h}{v}" for h, v in req.headers.items())
    headers_2 = "".join(f"{h}{v}" for h, v in req.unredirected_hdrs.items())

    the_str = "{}{}{}{}{}".format(
        req.get_method(),
        req.get_full_url(),
        headers_1,
        headers_2,
        req.get_data() or "",
    )

    return hashlib.sha256(the_str.encode("utf-8", "backslashreplace")).hexdigest()
