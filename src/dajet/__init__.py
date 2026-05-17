from os import environ

from dajet._platform import find_binary_folder

environ.setdefault ( "PYTHONNET_RUNTIME" , "coreclr" )

import clr  # noqa

for dll in "TypeSystem" , "Data" , "Metadata" :
	clr.AddReference ( str ( find_binary_folder ( ) / f"DaJet.{dll}.dll" ) )  # noqa

from DaJet.Metadata import MetadataProvider  # noqa
from DaJet.Data import DataSourceType  # noqa
from System import Guid  # noqa
from System.Collections.Generic import List  # noqa

__all__ = [ 'DataSourceType' , 'MetadataProvider' , 'Guid' , 'List' ]  # noqa

from sqlalchemy.dialects.postgresql import VARCHAR
from sqlalchemy.dialects.postgresql.base import ischema_names

# Регистрируем mvarchar как VARCHAR ДО вызова get_columns
ischema_names['mvarchar'] = VARCHAR
