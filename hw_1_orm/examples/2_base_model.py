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


if __name__ == '__main__':
    db.connect()
    db.drop_tables([User, Post])
    db.create_tables([User, Post])

    for i in range(1, 4):
        user = User(name=f'User_{i}')
        user.save()

    for i in range(1, 4):
        post = Post(text=f'this is text from post {i}')
        post.save()

    for user in User.select():
        print(user)

    for post in Post.select():
        print(post)
