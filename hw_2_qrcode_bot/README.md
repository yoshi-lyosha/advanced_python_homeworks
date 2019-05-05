# QR-code coupons distribution vk-bot

## What is that?

Just a hometask.

The main point was to create a little system that generates qr-codes images with coupons in one process and uploads it to the chat with client in another process.

## HOW TO USE

Just
```bash
docker-compose -f ./hw_2_qrcode_bot/docker_compose.yml up
```
from the root dir of this whole project

Don't forget to write your vk token to the `hw_2_qrcode_bot/hw_2.env` file as `VK_API_TOKEN=123` or pass it by `docker-compose run -e VK_API_TOKEN=123`

### How to scale?

Use
```bash
docker-compose -f ./hw_2_qrcode_bot/docker_compose.yml up --scale s2_qrcode_img_generator=6
```
or something like that

### How it became such big?

Pretty fast after couple of versions (of beers) 
```
version 3.0

       @@@@@@      ======      @@@@@@@      ========     @@@@@@@      ========      @@@       o
       coupon      coupon      QR-code      rendered     image        uploaded      vk       \|/
 .-->  gen    -->  queue  -->  image   -->  images   --> uploader --> images   -->  bot  <->  |
 |                             gen          queue                     data          app      / \
 |                                                                    queue          |       client
 |                                   ===========                                     |
 '---------------------------------- generate    ------------------------------------'
                                     tasks queue
                                           
=== - queue                                                  
@@@ - application 

General idea - generate new qrcode imgs on demand, but have some buffer in front of imgs consumer

=== generate tasks queue - feedback from vk bot app, tells that image was taken and we need compensate it
@@@ coupon generator - defines the coupon generation logic (random ids, limited set of ids, smth else)
=== coupon queue - str (just coupon like "SMOKE_WEED-420"
@@@ QR-code image generator - makes from coupons qr-code images
=== rendered images queue - bytes (just raw image bytes)
@@@ image uploader - uploads images to vk
=== uploaded images data queue - str (vk attachment id "<type><owner_id>_<media_id>")
@@@ vk bot app - just chat bot that can respond to client with qr-code coupon image

total: 
- 4 queues
- 4 services

pros of that number of services:
- each step logic encapsulated to a module:
    - coupon generation
    - image rendering
    - image uploading
  so it's can be hot reloaded without any latency in bot-client communication if buffer 
  of generated imgs is not empty
- qr-code image generator (cpu bound service) can be easily scaled as much as you want

cons:
- redundant complexity for such task :)
```


#### first versions
just for the history, don't pay attention
```
version 1.0

       @@@@@@@@@@       ========       @@@@@@@@@       ========      @@@@@@@       ========        @@@       o
       image            generate       QR-code         rendered      image         uploaded        vk       \|/
 .-->  uploading  --->  tasks    --->  image     --->  images   ---> uploader ---> images   ---->  bot  <->  |
 |     dispatcher       queue          generator       queue                       data            app      / \
 |                                                                                 queue            |       client
 |                                                                                                  |
 |                                             ?????????                                            |
 '--------------------------------------------------------------------------------------------------'
                two factors - number of ready images or feedback about its amount reducing
                
=== - queue
@@@ - application                
```

```
version 2.0

      ========       @@@@@@@@@       ========      @@@@@@@       ========        @@@       o
      generate       QR-code         rendered      image         uploaded        vk       \|/
 .--> tasks    --->  image     --->  images   ---> uploader ---> images   ---->  bot  <->  |
 |    queue          generator       queue                       queue           app      / \
 |                                                                                |       client
 '--------------------------------------------------------------------------------'
```
