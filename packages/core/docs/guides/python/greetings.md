# Greetings

The library's example features: `greet` builds a greeting, and `GreetingStore` keeps greetings in memory. Replace them with your own, keeping the shape of this page for each feature.

```python
from example_package import GreetingNotFoundError, GreetingStore, greet

greet("Ada")  # 'Hello, Ada!'

store = GreetingStore()
item = store.create("Ada")  # Greeting(id=1, name='Ada', message='Hello, Ada!')
store.update(item.id, "Grace")
store.list()  # [Greeting(id=1, name='Grace', message='Hello, Grace!')]
store.delete(item.id)

try:
    store.get(item.id)
except GreetingNotFoundError as error:
    print(error)  # greeting 1 not found
```

## `greet`

```python
def greet(name: str) -> str: ...
```

Returns `Hello, <name>!` with surrounding whitespace removed from `name`. Raises `ValueError` (`name must not be empty`) when `name` is empty or only whitespace.

## `GreetingStore`

An in-memory collection that stands in for your own storage. It is not thread-safe and keeps nothing between runs.

| Method | What it does | Raises |
| --- | --- | --- |
| `list()` | All greetings, oldest first. | |
| `get(id)` | One greeting. | `GreetingNotFoundError` if `id` does not exist. |
| `create(name)` | Adds a greeting and returns it, with the next id. | `ValueError` if `name` is empty. |
| `update(id, name)` | Replaces the name and message of a greeting. | `GreetingNotFoundError`, `ValueError`. |
| `delete(id)` | Removes a greeting. | `GreetingNotFoundError`. |

`Greeting` is an immutable dataclass with `id`, `name` and `message`. `GreetingNotFoundError` is a `LookupError`.

## Used by

The `hello` command of [`example-cli`](../../../../cli/docs/guides/cli/hello.md) calls `greet`. The [HTTP API](../../../../api/docs/api.md) keeps greetings in a `GreetingStore` and returns `GreetingNotFoundError` as `404`.
