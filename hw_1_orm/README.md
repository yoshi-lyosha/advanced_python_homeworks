# ORM

Here is simple peewee-like orm with base CRUD functionality, not production ready, without any long-term support, it's just an academic practice in meta-programming

### How to use

##### Model definition

At first, you must select your database driver

(currently only SQLite driver is implemented)
```python
from hw_1_orm.orm import SQLiteDBDriver

db = SQLiteDBDriver('some_test_1.db')
```

Next, you need to define your models

You can create a simple model with some fields
```python
from hw_1_orm.orm import Model, AutoField, CharField, SQLiteDBDriver

db = SQLiteDBDriver('1_simple.db')

class User(Model):
    id = AutoField()
    name = CharField()
    
    class Meta:
        database = db
```

You can create your local base model with connection and use it as other models base

```python
from hw_1_orm.orm import Model, AutoField, CharField, SQLiteDBDriver

db = SQLiteDBDriver('2_base_model.db')

class BaseModel(Model):
    class Meta:
        database = db
        
class User(BaseModel):
    id = AutoField()
    name = CharField()

class Post(BaseModel):
    text = CharField()

```

Also you can inherit from existent model with its fields and add something to that
```python
from hw_1_orm.orm import Model, AutoField, CharField, SQLiteDBDriver

db = SQLiteDBDriver('3_inheritance.db')

class ZooPet(Model):
    nickname = CharField()
    
    class Meta:
        database = db
    
class SponsoredZooPet(ZooPet):
    sponsor = CharField()
```

Notice, that you must declare Meta class in your model, that must have database attribute that will be an instance of DBDriver


After your database driver and your models are declared - you have to 

- connect to the database
- also you can drop all existent tables if u want (i will do that in each example for unlimited reproducibility)
- create tables

```python
from hw_1_orm.orm import Model, AutoField, CharField, SQLiteDBDriver

db = SQLiteDBDriver('some_test_2.db')

class User(Model):
    name = CharField()
    class Meta:
        database = db
        
db.connect()
db.create_tables([User])
```

##### data manipulations

There will be pretty long reproducible example of all data manipulations

```python
from hw_1_orm.orm import SQLiteDBDriver, Model, AutoField, IntegerField, CharField

db = SQLiteDBDriver('4_data_manipulations.db')


class User(Model):
    id = AutoField()
    name = CharField()
    age = IntegerField()

    class Meta:
        database = db


if __name__ == '__main__':
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
```
