URDF Import Extension [isaacsim.asset.importer.urdf]
####################################################

URDF Importer API
=================
The URDF importer provides a Python API for configuring and converting URDF files into USD assets.
Below is a sample demonstrating how to import the Carter URDF included with this extension.

.. code-block:: python
    :linenos:

    import os

    import omni.usd
    from isaacsim.asset.importer.urdf import URDFImporter, URDFImporterConfig

    # Get path to extension data.
    ext_manager = omni.kit.app.get_app().get_extension_manager()
    ext_id = ext_manager.get_enabled_extension_id("isaacsim.asset.importer.urdf")
    extension_path = ext_manager.get_extension_path(ext_id)

    urdf_path = os.path.join(extension_path, "data", "urdf", "robots", "carter", "urdf", "carter.urdf")
    output_dir = os.path.dirname(urdf_path)

    # Configure and import.
    import_config = URDFImporterConfig(
        urdf_path=urdf_path,
        usd_path=output_dir,
        collision_from_visuals=False,
        merge_mesh=False
    )

    importer = URDFImporter(import_config)
    output_path = importer.import_urdf()

    # Open the resulting USD stage.
    omni.usd.get_context().open_stage(output_path)

.. autoclass:: isaacsim.asset.importer.urdf.URDFImporter
    :members:
    :undoc-members:
    :no-show-inheritance:

.. autoclass:: isaacsim.asset.importer.urdf.URDFImporterConfig
    :members:
    :undoc-members:
    :no-show-inheritance:
