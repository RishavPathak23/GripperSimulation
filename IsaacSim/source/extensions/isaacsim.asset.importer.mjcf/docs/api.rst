MJCF Importer Extension [isaacsim.asset.importer.mjcf]
#######################################################

MJCF Import Workflow
====================
Use the MJCF importer configuration and converter classes to import MJCF files into USD.
Below is a sample demonstrating how to import the Ant MJCF included with this extension.

.. code-block:: python
    :linenos:

    import omni.usd
    from isaacsim.asset.importer.mjcf import MJCFImporter, MJCFImporterConfig
    from isaacsim.asset.importer.utils import stage_utils

    # Get path to extension data:
    ext_manager = omni.kit.app.get_app().get_extension_manager()
    ext_id = ext_manager.get_enabled_extension_id("isaacsim.asset.importer.mjcf")
    extension_path = ext_manager.get_extension_path(ext_id)

    # setting up import configuration:
    config = MJCFImporterConfig(mjcf_path=extension_path + "/data/mjcf/nv_ant.xml")

    # import MJCF
    importer = MJCFImporter(config)
    output_path = importer.import_mjcf()

    # open the resulting USD for inspection
    stage = stage_utils.open_stage(output_path)


.. autoclass:: isaacsim.asset.importer.mjcf.MJCFImporter
    :members:
    :undoc-members:
    :no-show-inheritance:

.. autoclass:: isaacsim.asset.importer.mjcf.MJCFImporterConfig
    :members:
    :undoc-members:
    :no-show-inheritance:
