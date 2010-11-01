# The MIT License
# 
# Copyright (c) 2010 Jeffrey Jenkins
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

from functools import wraps
from pymongo import ASCENDING, DESCENDING
from copy import copy, deepcopy

from mongoalchemy.fields import BadValueException
from mongoalchemy.query_expression import QueryField, QueryExpression, BadQueryException

class UpdateExpression(object):
    def __init__(self, query):
        self.query = query
        self.session = query.session
        self.update_data = {}
        self.__upsert = False
        self.__multi = False
    
    def upsert(self):
        ''' If a document matching the query doesn't exist, create one '''
        self.__upsert = True
        return self
    
    def multi(self):
        ''' Update multiple documents.  The Mongo default is to only update 
            the first matching document '''
        self.__multi = True
        return self
    
    def set(self, qfield, value):
        ''' Atomically set ``qfield`` to ``value``'''
        return self._atomic_op('$set', qfield, value)
    
    def unset(self, qfield):
        ''' Atomically delete the field ``qfield``
             .. note:: Requires server version **>= 1.3.0+**.
        '''
        # TODO: assert server version is >1.3.0
        return self._atomic_generic_op('$unset', qfield, True)
        
    def inc(self, qfield, value=1):
        ''' Atomically increment ``qfield`` by ``value`` '''
        return self._atomic_op('$inc', qfield, value)
        
    def append(self, qfield, value):
        ''' Atomically append ``value`` to ``qfield``.  The operation will 
            if the field is not a list field'''
        return self._atomic_list_op('$push', qfield, value)
        
    def extend(self, qfield, *value):
        ''' Atomically append each value in ``value`` to the field ``qfield`` '''
        return self._atomic_list_op_multivalue('$pushAll', qfield, *value)
        
    def remove(self, qfield, value):
        ''' Atomically remove ``value`` from ``qfield``'''
        return self._atomic_list_op('$pull', qfield, value)
        
    def remove_all(self, qfield, *value):
        ''' Atomically remove each value in ``value`` from ``qfield``'''
        return self._atomic_list_op_multivalue('$pullAll', qfield, *value)
    
    def add_to_set(self, qfield, value):
        ''' Atomically add ``value`` to ``qfield``.  The field represented by 
            ``qfield`` must be a set
            
            .. note:: Requires server version **1.3.0+**.
        '''
        # TODO: check version > 1.3.3
        return self._atomic_list_op('$addToSet', qfield, value)
    
    def pop_last(self, qfield):
        ''' Atomically pop the last item in ``qfield.``
            .. note:: Requires version **1.1+**'''
        return self._atomic_generic_op('$pop', qfield, 1)
    
    def pop_first(self, qfield):
        ''' Atomically pop the first item in ``qfield.``
            .. note:: Requires version **1.1+**'''
        return self._atomic_generic_op('$pop', qfield, -1)
    
    def _atomic_list_op_multivalue(self, op, qfield, *value):
        if op not in qfield.get_type().valid_modifiers:
            raise InvalidModifierException(qfield.get_type(), op)
        wrapped = []
        for v in value:
            wrapped.append(qfield.get_type().item_type.wrap(v))
        if op not in self.update_data:
            self.update_data[op] = {}
        self.update_data[op][qfield.get_name()] = value
        return self
    
    def _atomic_list_op(self, op, qfield, value):
        if op not in qfield.get_type().valid_modifiers:
            raise InvalidModifierException(qfield.get_type(), op)
        
        if op not in self.update_data:
            self.update_data[op] = {}
        self.update_data[op][qfield.get_name()] = qfield.get_type().child_type().wrap(value)
        return self
    
    def _atomic_op(self, op, qfield, value):
        if op not in qfield.get_type().valid_modifiers:
            raise InvalidModifierException(qfield.get_type(), op)

        if op not in self.update_data:
            self.update_data[op] = {}
        self.update_data[op][qfield.get_name()] = qfield.get_type().wrap(value)
        return self
    
    def _atomic_generic_op(self, op, qfield, value):
        if op not in qfield.get_type().valid_modifiers:
            raise InvalidModifierException(qfield.get_type(), op)
        
        if op not in self.update_data:
            self.update_data[op] = {}
        self.update_data[op][qfield.get_name()] = value
        return self
    
    def get_upsert(self):
        return self.__upsert
    
    def get_multi(self):
        return self.__multi
    
    def execute(self):
        ''' Execute the update expression on the database '''
        self.session.execute_update(self)

class UpdateException(Exception):
    ''' Base class for exceptions related to updates '''
    pass

class InvalidModifierException(UpdateException):
    ''' Exception raised if a modifier was used which isn't valid for a field '''
    def __init__(self, field, op):
        UpdateException.__init__(self, 'Invalid modifier for %s field: %s' % (field.__class__.__name__, op))

class ConflictingModifierException(UpdateException):
    ''' Exception raised if conflicting modifiers are being used in the 
        update expression '''
    pass