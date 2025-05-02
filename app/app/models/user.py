#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Modelo de usuario para la SOA Database
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime

@dataclass
class User:
    """
    Clase que representa un usuario en el sistema.
    """
    id: str
    username: str
    email: str
    provider: str  # google, facebook, microsoft
    provider_id: str
    role: str  # admin, editor, viewer
    created_at: datetime
    last_login: Optional[datetime] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'User':
        """
        Crea una instancia de Usuario a partir de un diccionario.
        
        Args:
            data: Diccionario con los datos del usuario
        
        Returns:
            User: Instancia de Usuario
        """
        created_at = datetime.fromisoformat(data['created_at']) if isinstance(data['created_at'], str) else data['created_at']
        last_login = None
        if data.get('last_login'):
            last_login = datetime.fromisoformat(data['last_login']) if isinstance(data['last_login'], str) else data['last_login']
        
        return cls(
            id=data['id'],
            username=data['username'],
            email=data['email'],
            provider=data['provider'],
            provider_id=data['provider_id'],
            role=data['role'],
            created_at=created_at,
            last_login=last_login
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convierte la instancia a un diccionario.
        
        Returns:
            Dict[str, Any]: Diccionario con los datos del usuario
        """
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'provider': self.provider,
            'provider_id': self.provider_id,
            'role': self.role,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }
    
    @property
    def is_admin(self) -> bool:
        """
        Verifica si el usuario es administrador.
        
        Returns:
            bool: True si es administrador, False en caso contrario
        """
        return self.role == 'admin'
    
    @property
    def is_editor(self) -> bool:
        """
        Verifica si el usuario es editor.
        
        Returns:
            bool: True si es editor, False en caso contrario
        """
        return self.role in ['admin', 'editor']
    
    @property
    def is_viewer(self) -> bool:
        """
        Verifica si el usuario es visualizador.
        
        Returns:
            bool: True si es visualizador, False en caso contrario
        """
        return self.role in ['admin', 'editor', 'viewer']