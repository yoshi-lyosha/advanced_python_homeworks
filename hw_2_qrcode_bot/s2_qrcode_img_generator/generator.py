import os
import base64
import io

import imgkit
import qrcode
import jinja2

# some measurements

"""
efficiency
    ^
650 |                                                                *
625 |                            *           *  *  *  *  *  *  *  *        *
600 | ~~~~~~~~~~~~~~~~~~~~~~~ *     *  *  *                             *     *
575 |                      *  :
550 |                         :
525 |                   *     :
500 |                 *       :
475 |               *         :
450 |             *           :
425 |         *               :
400 |           *             :
375 |                         :
350 |       *                 :
325 |                         :
300 |                         :
275 |     *                   :
250 |                         :
225 |                         :
200 |   *                     :
175 |                         :
150 |                         :
125 |                         :
100 | *                       :
75  |                         :
50  |                         :
25  |                         :
0   |                         :                             number of processes
-------------------------------------------------------------------------------->
    0 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 30 31 32


"""

# pool/jobs | time             | efficiency, %
#  1          877 ms ± 4.88 ms   100
#  2          916 ms ± 9.88 ms   191
#  3          959 ms ± 15.5 ms   274
#  4          992 ms ± 15.1 ms   354
#  5          1.06 s ± 17.2 ms   436

#  6          1.28 s ± 15.8 ms   411
#  7          1.36 s ± 21.4 ms   451
#  8          1.5 s ± 14.3 ms    468
#  9          1.56 s ± 17.4 ms   506
#  10         1.63 s ± 20.6 ms   538

#  11         1.65 s ± 22.9 ms   585
#  12         1.73 s ± 39.9 ms   608
#  13         1.82 s ± 28.8 ms   626
#  14         2.02 s ± 24.8 ms   608
#  15         2.19 s ± 25 ms     601

#  16         2.31 s ± 19.4 ms   607
#  17         2.56 s ± 57.9 ms   582
#  18         2.61 s ± 55.7 ms   605
#  19         2.68 s ± 35.3 ms   622
#  20         2.77 s ± 59.7 ms   633

#  21         2.95 s ± 80.6 ms   624
#  22         3.09 s ± 77 ms     624
#  23         3.17 s ± 161 ms    636
#  24         3.34 s ± 163 ms    630
#  25         3.42 s ± 144 ms    641

#  30         4.31 s ± 217 ms    610
#  31         4.32 s ± 131 ms    629
#  32         4.64 s ± 150 ms    605


class JinjaTemplater:
    """ You can template html by jinja """

    def __init__(self, html_template_path):
        self.template = jinja2.Template(open(html_template_path).read())

    def render_html_with_qr_code(self, qr_code_in_b64):
        # 13.4 µs ± 121 ns
        return self.template.render(qr_code=qr_code_in_b64)


class StrTemplater:
    """ Or you can template html just by str.replace() which is twice faster """

    def __init__(self, html_template_path):
        self.template = open(html_template_path).read()

    def render_html_with_qr_code(self, qr_code_in_b64):
        # 7.36 µs ± 38.1 ns
        return self.template.replace("{{ qr_code }}", qr_code_in_b64)


class QRCodeImgGenerator:
    """ Generator of images with qr-codes, you can find some usage at the end of file """

    def __init__(
        self,
        html_template_path: str,
        img_height: int,
        img_width: int,
        templater=StrTemplater,
    ):
        # some inputs validation
        if not os.path.exists(html_template_path):
            raise RuntimeError(f"Invalid html template path ({html_template_path})")
        if not (img_height > 0 and img_width > 0):
            raise RuntimeError(f"Img size must be > 0 ({img_height}, {img_width})")

        # jinja is cool, but str is more preferable cuz jinja can't be pickled :c
        self.templater = templater(html_template_path)

        self.imgkit_options = {
            "height": img_height,
            "width": img_width,
            "quality": 100,  # for more heat producing
            # disable stdout of imgkit
            "quiet": None,
        }

    def generate_qr_code_img(self, qr_code_data: str) -> bytes:
        # 886 ms ± 6.77 ms

        # creating qr-code image and packing it with base64
        img = qrcode.make(qr_code_data)  # returns pillow image

        buffer = io.BytesIO()
        img.save(buffer)  # the only way to get image binary

        img_in_b64 = base64.b64encode(buffer.getvalue())
        img_in_b64 = img_in_b64.decode()  # bc base64.b64encode returns bytes

        # filling the template css .img.url property
        qrcode_html = self.templater.render_html_with_qr_code(img_in_b64)

        # creating jpg by imgkit(wkhtmltopdf)
        img = imgkit.from_string(qrcode_html, False, options=self.imgkit_options)

        return img


if __name__ == "__main__":
    from concurrent.futures.process import ProcessPoolExecutor

    html_template_file_name = "qr_code_img_template.html"
    path_to_template = os.path.join(os.path.dirname(__file__), html_template_file_name)
    qr_code_img_gen = QRCodeImgGenerator(path_to_template, 600, 600)

    # simple_usage
    print(qr_code_img_gen.generate_qr_code_img("кто прочитал - тот пидор"))

    # not_so_simple_usage
    n_workers = 4
    with ProcessPoolExecutor(n_workers) as executor:
        data_to_gen = (f"img_{i}" for i in range(n_workers))
        res = executor.map(qr_code_img_gen.generate_qr_code_img, data_to_gen)
        print(list(res))
