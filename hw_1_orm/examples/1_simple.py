from hw_1_orm.orm import Model, AutoField, CharField, SQLiteDBDriver

db = SQLiteDBDriver('1_simple.db')


class User(Model):
    id = AutoField()
    name = CharField()

    class Meta:
        database = db


if __name__ == '__main__':
    db.connect()
    db.drop_tables([User])
    db.create_tables([User])

    user_1 = User(name='User_1')
    user_1.save()

    for user in User.select():
        print(user)
