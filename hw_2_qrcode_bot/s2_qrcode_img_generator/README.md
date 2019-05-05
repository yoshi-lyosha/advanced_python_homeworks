### QR-code images generator
1. generates qr code with some data
2. encodes it to the base 64
3. puts it into the html template with arrows
4. generates jpg from html using webkit and black cpu-heating magic 

### TODO ideas 
- to use asyncio
    - perform actions in subroutines
    - use ProcessPoolExecutor and loop.run_in_executor (it will be pretty fast ast shows graph in `hw_2_qrcode_bot/s2_qrcode_img_generator/generator.py` (see it, it's neat))
