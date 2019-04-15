# behold Yet Another ORM

# original skeleton for this project is located on
# https://github.com/alexopryshko/advancedpython/blob/master/2/orm.py
import logging
import sqlite3
from dataclasses import dataclass
from typing import List, Type


class Field:
    """ Base class for all orm fields """
    def __init__(self, primary=False, null=False, default=None):
        self.primary = primary
        self.null = null
        self.default = default

        self.name: str = None  # will be defined in ModelMeta

        self.is_primary_key_sql = 'PRIMARY KEY' if primary else ''

    def validate(self, value):
        if value is None and not self.null:
            raise ValueError(f'Null values are not allowed for {type(self).__name__} in {self.name}')

        self._validate(value)

        return value

    def _validate(self, value):
        raise NotImplementedError

    def get_column_sql(self):
        raise NotImplementedError

    # for other types of filtering you can implement other comparison methods
    def __eq__(self, other):
        return f"{self.name} = '{other}'"


class IntegerField(Field):
    """ Integer field """
    def __init__(self, primary=False, null=False, default=None):
        super().__init__(primary, null, default)

    def _validate(self, value):
        if not self.null and not isinstance(value, int):
            raise ValueError(f'{type(self).__name__} value {value!r} is not int')

    def get_column_sql(self):
        return f'{self.name} INT {self.is_primary_key_sql}'


class AutoField(Field):
    """ Primary auto-incremental integer field """
    def __init__(self, primary=True, null=True, default=None):
        super().__init__(primary, null, default)

    def _validate(self, value):
        if self.null and value is not None:
            raise ValueError(f'{type(self).__name__} doesn\'t expect any value assign')

    def get_column_sql(self):
        return f'{self.name} INTEGER {self.is_primary_key_sql} AUTOINCREMENT'


class CharField(Field):
    """ Char field """
    def __init__(self, max_length=255, primary=False, null=False, default=None):
        self.max_length = max_length
        super().__init__(primary, null, default)

    def _validate(self, value):
        if not self.null and not isinstance(value, str):
            raise ValueError(f'{type(self).__name__} value {value!r} is not str')

    def get_column_sql(self):
        return f'{self.name} VARCHAR({self.max_length}) {self.is_primary_key_sql}'


class _ConnectionState:
    """ Just container for connection storing """
    def __init__(self):
        self.closed = True
        self.conn = None

        self.reset()

    def reset(self):
        self.closed = True
        self.conn = None

    def set_connection(self, conn):
        self.conn = conn
        self.closed = False


class DBDriver:
    """ Base database driver """
    def __init__(self, database, connect_params=None):
        self.database = database
        self.connect_params = connect_params or {}

        self._state = _ConnectionState()

    def _connect(self):
        raise NotImplementedError

    def connect(self):
        if not self._state.closed:
            raise RuntimeError("Already connected")

        self._state.reset()
        self._state.set_connection(self._connect())

    def rollback(self):
        return self._state.conn.rollback()

    def commit(self):
        return self._state.conn.commit()

    def execute_sql(self, sql, params=None):
        cursor = self._state.conn.cursor()
        try:
            logging.debug(sql)
            cursor.execute(sql, params or ())
        except Exception:
            self.rollback()
            raise
        else:
            self.commit()
        return cursor

    @staticmethod
    def last_insert_id(cursor):
        return cursor.lastrowid

    @staticmethod
    def create_tables(models: List[Type["Model"]]):
        for model in models:
            model.create_table()

    @staticmethod
    def drop_tables(models: List[Type["Model"]]):
        for model in models:
            model.drop_table()

    def table_exists(self, table_name, schema='main'):
        return table_name in self.get_tables(schema=schema)

    def get_tables(self, schema='main'):
        raise NotImplementedError


class SQLiteDBDriver(DBDriver):
    """ Sqlite db driver implementation """
    def __init__(self, database, connect_params=None, timeout=5):
        super().__init__(database, connect_params)
        self._timeout = timeout

    def _connect(self):
        conn = sqlite3.connect(self.database, timeout=self._timeout,
                               **self.connect_params)
        return conn

    def get_tables(self, schema='main'):
        cursor = self.execute_sql(
            f'SELECT name FROM {schema}.sqlite_master WHERE type=?', ('table',)
        )
        return [row for row, in cursor.fetchall()]


@dataclass
class Metadata:
    """ Model class meta container """
    database: DBDriver
    fields: dict
    table_name: str
    pk_name: str
    pk_field: Field


class ModelMeta(type):
    """
    Model meta-class.

    the main thing is the tricks with fields, mro, and some validations
    """
    def __new__(mcs, name, bases, namespace):  # NOSONAR
        if name == 'Model':
            return super().__new__(mcs, name, bases, namespace)

        # mro walk
        base_meta = None
        base_fields = {}
        for base in bases:
            if not issubclass(base, Model):
                continue
            base_meta = getattr(base, 'Meta', None)
            if base_meta is None:
                continue
            base_class_meta: Metadata = getattr(base, 'meta', None)
            if base_class_meta is None:
                continue  # weird flex but ok
            base_fields.update(base_class_meta.fields)

        # validation
        meta = namespace.get('Meta')
        if meta is None:
            if base_meta is None:
                raise ValueError(f'There is no .Meta class in {name} and its bases')
            else:
                meta = base_meta
        if not hasattr(meta, 'database'):
            raise ValueError(f'There is no "database" attr in {name}.Meta')

        fields = {k: v for k, v in namespace.items()
                  if isinstance(v, Field)}

        # updating base fields by new
        base_fields.update(fields)
        fields = base_fields

        primary_keys = []
        for field_name, field in fields.items():
            field.name = field_name
            if field.primary:
                primary_keys.append(field)  # filtering primary guys

        # validation of primary keys
        if len(primary_keys) > 1:
            raise AttributeError(
                f'There is more than 1 primary key in model {name}'
            )
        elif len(primary_keys) == 0:
            pk = AutoField()
            pk_name = 'id'
            pk.name = pk_name
            fields[pk_name] = pk
        else:
            pk = primary_keys[0]
            if not any(isinstance(pk, t) for t in [AutoField]):
                raise ValueError(
                    f'Field {pk} is not supported as primary key'
                )
            pk_name = pk.name

        # initialization of meta container
        model_meta = Metadata(
            database=meta.database,
            fields=fields,
            table_name=name.lower(),
            pk_name=pk_name,
            pk_field=pk
        )
        namespace['meta'] = model_meta

        return super().__new__(mcs, name, bases, namespace)


class Query:
    """ Base class for query """
    def __init__(self, model_cls: Type["Model"]):
        self.model_cls = model_cls
        self.sql = None

    def execute(self, database):
        return self._execute(database)

    def _execute(self, database):
        raise NotImplementedError


class ResultIterator:
    """ Iterator wrapper for cursor wrappers (currently is not used) """
    def __init__(self, cursor_wrapper):
        self.cursor_wrapper = cursor_wrapper
        self.index = 0

    def __iter__(self):
        return self

    def next(self):
        self.index += 1
        return self.cursor_wrapper.iterate()

    __next__ = next


class CursorWrapper:
    """ Cursor wrapper for iteration row by row with some logic """
    def __init__(self, cursor):
        self.cursor = cursor
        self.count = 0
        self.initialized = False

    def initialize(self):
        pass

    def iterate(self):
        row = self.cursor.fetchone()
        if row is None:
            self.cursor.close()
            raise StopIteration
        elif not self.initialized:  # ?
            self.initialize()  # Lazy initialization.
            self.initialized = True
        self.count += 1
        result = self.process_row(row)
        return result

    def process_row(self, row):
        return row

    def iterator(self):
        while True:
            try:
                yield self.iterate()
            except StopIteration:
                return

    def __iter__(self):
        return self.iterator()

    def __getitem__(self, item):
        if isinstance(item, int):
            return list(self)[item]
        else:
            raise ValueError('CursorWrapper only supports integer indexes')


class DictCursorWrapper(CursorWrapper):
    """ Cursor wrapper, that wraps every row in dict """
    def _initialize_columns(self):
        description = self.cursor.description
        self.columns = [t[0][t[0].find('.') + 1:].strip('"')  # feature for complicated description
                        for t in description]
        self.ncols = len(description)

    initialize = _initialize_columns

    def _row_to_dict(self, row):
        result = {}
        for i in range(self.ncols):
            result.setdefault(self.columns[i], row[i])  # Do not overwrite.
        return result

    process_row = _row_to_dict


class ModelObjectCursorWrapper(DictCursorWrapper):
    """ Cursor wrapper, that wraps every row in model object """
    def __init__(self, cursor, model_cls: Type["Model"]):
        super().__init__(cursor)
        self.model_cls = model_cls

    def process_row(self, row):
        row = super().process_row(row)

        pk_name = self.model_cls.meta.pk_name
        pk_value = row.pop(pk_name)

        row = self.model_cls(**row)
        row._pk = pk_value
        setattr(row, pk_name, pk_value)
        return row


class SelectQuery(Query):
    """
    Select query, allows usage like Model.select().where(expression)

    methods todo:
    .filter()
    .group_by()
    .other_stuff()
    """
    def __init__(self, model_cls: Type["Model"], sql=None):
        super().__init__(model_cls)
        self.fields_names = ','.join(self.model_cls.meta.fields)
        self.sql = sql or f'SELECT {self.fields_names} FROM {self.model_cls.meta.table_name}'

    def _execute(self, database):
        cursor = self.model_cls.meta.database.execute_sql(self.sql)
        return ModelObjectCursorWrapper(cursor, self.model_cls)

    def where(self, expression):
        # todo: avoid sqlinj in where construction, lol
        self.sql = f'SELECT {self.fields_names} FROM {self.model_cls.meta.table_name} WHERE {expression}'
        return self

    def __iter__(self):
        return iter(self.execute(self.model_cls.meta.database))

    def get(self):
        # todo: handle DoesNotExists case
        return self.execute(self.model_cls.meta.database)[0]


class InsertQuery(Query):
    """ Insert query """
    def __init__(self, model_cls, **insert_fields):
        super().__init__(model_cls)
        self.insert_fields = insert_fields

    def _execute(self, database: "DBDriver"):
        meta = self.model_cls.meta

        # filtering autoincrement keys
        fields = [f_name for f_name, f in meta.fields.items() if not isinstance(f, AutoField)]
        values = [self.insert_fields[f_name] for f_name in fields]

        fields = ','.join(str(v) for v in fields)
        values = ','.join(repr(v) for v in values)

        sql = f'INSERT INTO {meta.table_name}({fields}) VALUES ({values})'

        cursor = database.execute_sql(sql)
        last_insert_id = database.last_insert_id(cursor)
        return last_insert_id


class UpdateQuery(Query):
    """ Update query """
    def __init__(self, model_cls, **update_fields):
        super().__init__(model_cls)
        self.insert_fields = update_fields
        self.sql = None  # todo

    def where(self, expression):
        meta = self.model_cls.meta

        # filtering autoincrement keys
        fields = [f_name for f_name, f in meta.fields.items() if not isinstance(f, AutoField)]
        values = [self.insert_fields[f_name] for f_name in fields]

        update_set_sql = ', '.join(
            f'{f_name} = {f_value!r}'
            for f_name, f_value in zip(fields, values)
        )

        self.sql = f'UPDATE {meta.table_name} SET {update_set_sql} WHERE {expression}'
        return self

    def _execute(self, database):
        cursor = database.execute_sql(self.sql)
        last_insert_id = database.last_insert_id(cursor)
        return last_insert_id


class DeleteQuery(Query):
    """ Delete query """
    def __init__(self, model_cls):
        super().__init__(model_cls)
        self.sql = None  # todo

    def where(self, expression):
        self.sql = f'DELETE FROM {self.model_cls.meta.table_name} WHERE {expression}'
        return self

    def _execute(self, database):
        cursor = database.execute_sql(self.sql)
        last_insert_id = database.last_insert_id(cursor)
        return last_insert_id


class TableSchema:
    """ Class for table schema generation """
    def __init__(self, model_cls: Type["Model"]):
        self.model_cls = model_cls
        self.database = model_cls.meta.database

    def create_table(self):
        # todo: if safe - check for IF NOT EXISTS if it's really worth it
        meta = self.model_cls.meta
        columns = []
        for field_name, field in meta.fields.items():
            columns.append(field.get_column_sql())
        columns = ', '.join(columns)
        sql = f'CREATE TABLE IF NOT EXISTS {self.model_cls.meta.table_name} ({columns})'
        return sql

    def drop_table(self):
        sql = f'DROP TABLE {self.model_cls.meta.table_name}'
        return sql


class Model(metaclass=ModelMeta):
    """ Base class for all orm models """
    meta: Metadata

    def __init__(self, *_, **kwargs):
        for field_name, field in self.meta.fields.items():
            value = field.validate(kwargs.get(field_name))
            setattr(self, field_name, value)

        self._pk = None

    @classmethod
    def create_table(cls):
        sql = TableSchema(cls).create_table()
        return cls.meta.database.execute_sql(sql)

    @classmethod
    def insert(cls, **insert_fields):
        return InsertQuery(cls, **insert_fields)

    @classmethod
    def update(cls, **update_fields):
        return UpdateQuery(cls, **update_fields)

    @classmethod
    def create(cls, **kwargs):
        inst = cls(**kwargs)
        inst.save()
        return inst

    @classmethod
    def select(cls):
        return SelectQuery(cls)

    @classmethod
    def get(cls, expression) -> "Model":
        return SelectQuery(cls).where(expression).get()

    @classmethod
    def delete(cls):
        return DeleteQuery(cls)

    def delete_instance(self):
        return self.delete().where(self._pk_expr()).execute(self.meta.database)

    def save(self):
        field_dict = {f_name: getattr(self, f_name) for f_name in self.meta.fields}
        if not self._pk:
            last_insert_id = self.insert(**field_dict).execute(self.meta.database)
            self._pk = last_insert_id
            setattr(self, self.meta.pk_name, self._pk)
            return 1
        else:
            self.update(**field_dict).where(self._pk_expr()).execute(self.meta.database)
            return 1

    def __repr__(self):
        model_name = type(self).__name__
        kwargs = ', '.join(f'{f}={getattr(self, f, None)!r}' for f in sorted(self.meta.fields))
        return f'{model_name}({kwargs})'

    def _pk_expr(self):
        # util for using .where for current obj
        return self.meta.pk_field == self._pk

    @classmethod
    def table_exists(cls):
        table_name = cls.meta.table_name
        return cls.meta.database.table_exists(table_name)

    @classmethod
    def drop_table(cls):
        if cls.table_exists():
            sql = TableSchema(cls).drop_table()
            return cls.meta.database.execute_sql(sql)
        else:
            return None
