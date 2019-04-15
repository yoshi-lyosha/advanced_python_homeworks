from hw_1_orm.orm import SQLiteDBDriver, Model, AutoField, IntegerField, CharField

db = SQLiteDBDriver('4_data_manipulations.db')


class User(Model):
    id = AutoField()
    name = CharField()
    age = IntegerField()

    class Meta:
        database = db


if __name__ == '__main__':
    # you can uncomment that for peeking on raw sql queries if you want
    # import logging
    # logging.basicConfig(level=logging.DEBUG)

    # at first you need to connect to db and create its tables
    db.connect()
    db.drop_tables([User])
    db.create_tables([User])

    # Create

    # you can create object at first and call its .save() method
    user_1 = User(name='User 1', age=24)
    user_1.save()
    # or you can use model .create() method that just a shortcut
    user_2 = User.create(name='User 2', age=42)

    # lets create some more users in for loop
    for i in range(3, 6):
        User.create(name=f'User {i}', age=42)

    # Read

    # you can select users by .where method that except an expression as its argument
    # .get() will return the first occurrence of the query set
    user_3 = User.select().where(User.name == 'User 3').get()

    # also you can use a shortcut for the previous case with single row select
    user_4 = User.get(User.name == 'User 4')

    # if you want to select more then one row use iteration
    users_with_age_42 = list(User.select().where(User.age == 42))

    # or if you want to select all
    all_users = list(User.select())

    # Update

    # here's pretty easy usage, you cat just change your model object and call .save()
    user_4.age = 420
    user_4.save()

    # also you can call Model.update() directly, but i doesn't recommend that, because
    # it's signature can be changed.
    User.update(name='Updated User 5', age=1488).where(User.id == 5).execute(User.meta.database)

    # Delete

    # here is also two ways - calling instance method directly
    user_2.delete_instance()

    # or calling Model.delete() query, but again - it's not recommended cuz signature can change
    User.delete().where(User.name == 'User 3').execute(User.meta.database)  # again it's a weird flex but ok

    # Finally let's print all table rows and check what we've done
    for user in User.select():
        # User 2 and User 3 are deleted, User 4 and User 5 are updated
        print(user)

