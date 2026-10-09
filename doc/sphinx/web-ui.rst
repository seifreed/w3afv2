Web user interface
==================

``w3af`` ships a web user interface which is served together with the
:doc:`REST API <api/index>`. Start it by running:

.. code-block:: console

    $ ./w3af_gui

The web service listens on ``127.0.0.1:5000`` by default, prints the URL of the
user interface (``https://127.0.0.1:5000/ui/``) and opens it in your default
browser. HTTPS uses a self-signed certificate stored in ``~/.w3af/ssl/``.

``w3af_gui`` accepts the same options as ``w3af_api``:

.. code-block:: console

    $ ./w3af_gui 127.0.0.1:8080 --no-ssl --no-browser
    $ ./w3af_gui -p <SHA512 hash of the password> -u admin
    $ ./w3af_gui -c config.yml

``--no-browser`` skips opening the browser. When a password is configured the
browser asks for the HTTP basic authentication credentials, which are then used
for every REST API call made by the user interface.

.. warning::

   Binding the service to a public address exposes the scanner to the network.
   Always configure a password when doing so.

Features
--------

 * **Scan**: enter the target URLs, choose a profile, enable or disable plugins
   (each plugin shows its description and options), edit the profile contents
   directly and start the scan.
 * **Status**: progress, ETA, requests per minute, active plugins and queues.
   The scan bar allows pausing, resuming, stopping and clearing the scan.
 * **Log**: the scan log, updated while the scan runs, filtered by message type.
 * **Findings**: the vulnerabilities and information stored in the knowledge
   base, with description, fix guidance, references and links to the HTTP
   traffic.
 * **URLs**: the URLs discovered during the scan.
 * **Traffic**: the HTTP request and response for any request ID.
 * **Exceptions**: errors raised by plugins during the scan, with tracebacks.

The interface is a static page which only talks to the REST API, it works in
any modern browser, at any screen width.
