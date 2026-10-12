# example-method — a stand-in method plugin

A minimal method plugin shipped with the framework's examples. It fills the
method slots of `examples/login-product` whose method the framework has not
written yet (`design`, `apply`, `verify`) so the slice runs without depending on an external method. It is not
a real method: a product configures its own plugin in `qf.yaml`.
