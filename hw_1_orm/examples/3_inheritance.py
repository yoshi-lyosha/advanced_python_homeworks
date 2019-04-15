from hw_1_orm.orm import Model, AutoField, CharField, SQLiteDBDriver

db = SQLiteDBDriver('3_inheritance.db')


class ZooPet(Model):
    nickname = CharField()

    class Meta:
        database = db


class SponsoredZooPet(ZooPet):
    sponsor = CharField()


if __name__ == '__main__':
    db.connect()
    db.drop_tables([ZooPet, SponsoredZooPet])
    db.create_tables([ZooPet, SponsoredZooPet])

    for i in range(1, 4):
        pet = ZooPet.create(nickname=f'Zoo_pet_nickname_{i}')

    for i in range(1, 4):
        sponsored_pet = SponsoredZooPet.create(
            nickname=f'Sponsored_zoo_pet_nickname_{i}',
            sponsor=f'Sponsor_{4 - i}'
        )

    for pet in ZooPet.select():
        print(pet)

    for pet in SponsoredZooPet.select():
        print(pet)
