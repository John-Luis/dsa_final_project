"""Explicit DSA implementations used by the service, independent of Flask/SQLite."""
from dataclasses import dataclass


@dataclass
class Node:
    value: dict
    previous: 'Node | None' = None
    next: 'Node | None' = None


class RequestQueue:
    """FIFO doubly linked list with an O(1) dictionary index by request ID.

    Construct from SQL rows in arrival order. Removal and neighbor lookup are O(1);
    finding the first eligible program is O(n), preserving FIFO within that program.
    SQLite remains the source of truth, so restarts and multiple workers are safe.
    """
    def __init__(self, records=()):
        self.head = self.tail = None
        self.index = {}
        for record in records:
            self.append(dict(record))

    def append(self, record):
        key = record['id']
        if key in self.index:
            raise ValueError('Duplicate request ID')
        node = Node(record, previous=self.tail)
        if self.tail:
            self.tail.next = node
        else:
            self.head = node
        self.tail = node
        self.index[key] = node

    def remove(self, key):
        node = self.index.pop(key)
        if node.previous:
            node.previous.next = node.next
        else:
            self.head = node.next
        if node.next:
            node.next.previous = node.previous
        else:
            self.tail = node.previous
        return node.value

    def neighbors(self, key):
        node = self.index[key]
        return (node.previous.value if node.previous else None,
                node.next.value if node.next else None)

    def first(self, program=None):
        node = self.head
        while node:
            if program is None or node.value['program'] == program:
                return node.value
            node = node.next
        return None

    def to_list(self):
        result, node = [], self.head
        while node:
            result.append(node.value)
            node = node.next
        return result
