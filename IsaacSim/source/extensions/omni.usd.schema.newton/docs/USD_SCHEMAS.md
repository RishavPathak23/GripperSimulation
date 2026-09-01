# USD Schemas

## newton_usd_schemas

### NewtonSceneAPI
NewtonSceneAPI applies on top of a PhysicsScene Prim, providing attributes to control a Newton Solver.

#### newton:maxSolverIterations
  Maximum number of iterations of the physics solver.
  
  If set to -1, each solver is free to choose an appropriate default.
  
  Range: [-1, inf)
  Units: dimensionless

#### newton:timeStepsPerSecond
  Simulation time step frequency in Hz.
  
  Range: [1, inf)
  Units: hertz

#### newton:gravityEnabled
  Whether gravity should be enabled or disabled in the simulation.
  
  This is intentionally separated from the gravity direction and magnitude
  to allow temporary disabling of gravity without modifying & caching values.


### NewtonXpbdSceneAPI
Provides Newton's XPBD (eXtended Position-Based Dynamics) solver configuration.

#### newton:xpbd:softBodyRelaxation
  Relaxation multiplier for tetrahedral FEM constraint corrections.
  
  Scales the computed position correction for tetrahedral soft body constraints.
  Lower values improve stability but require more iterations for convergence.
  
  Range: [0, 1]
  Units: dimensionless

#### newton:xpbd:softContactRelaxation
  Relaxation multiplier for soft contact constraint corrections.
  
  Scales the computed position correction for particle-particle and particle-shape
  contacts. Lower values improve stability but require more iterations for convergence.
  
  Range: [0, 1]
  Units: dimensionless

#### newton:xpbd:jointLinearRelaxation
  Relaxation multiplier for joint linear constraint corrections.
  
  Scales the computed position correction for joint linear (positional) constraints.
  Lower values improve stability for complex kinematic chains but slow convergence.
  
  Range: [0, 1]
  Units: dimensionless

#### newton:xpbd:jointAngularRelaxation
  Relaxation multiplier for joint angular constraint corrections.
  
  Scales the computed rotation correction for joint angular (rotational) constraints.
  Lower values improve stability but slow convergence.
  
  Range: [0, 1]
  Units: dimensionless

#### newton:xpbd:jointLinearCompliance
  Compliance for joint linear constraints.
  
  Inverse stiffness for joint linear constraints. Added to denominator in constraint
  solver. Zero creates rigid constraints. Higher values create softer, springy joints.
  
  Range: [0, inf)
  Units: second * second / mass

#### newton:xpbd:jointAngularCompliance
  Compliance for joint angular constraints.
  
  Inverse stiffness for joint angular constraints. Added to denominator in constraint
  solver. Zero creates rigid constraints. Higher values create softer, springy joints.
  
  Range: [0, inf)
  Units: degrees * second * second / (mass * distance * distance)

#### newton:xpbd:rigidContactRelaxation
  Relaxation multiplier for rigid body contact constraint corrections.
  
  Scales the computed correction for rigid body contacts including normal, friction,
  torsional friction, and rolling friction. Lower values improve stability for
  stacking but require more iterations.
  
  Range: [0, 1]
  Units: dimensionless

#### newton:xpbd:rigidContactConWeighting
  Enable contact constraint weighting for rigid bodies.
  
  When enabled, tracks the number of contacts per body and uses this information
  to distribute contact corrections more evenly across multiple simultaneous contacts.

#### newton:xpbd:angularDamping
  Angular velocity damping coefficient.
  
  Applied during rigid body integration as velocity *= (1 - damping * dt). Higher
  values cause rotational motion to decay faster.
  
  Range: [0, inf)
  Units: 1 / seconds

#### newton:xpbd:restitutionEnabled
  Whether restitution is enabled for contacts.
  
  When enabled, applies velocity corrections after constraint solving to simulate
  elastic collisions. Restitution coefficients are read from material properties.


### NewtonKaminoSceneAPI
Provides Newton's Kamino solver configuration.

#### newton:kamino:padmm:primalTolerance
  The tolerance on the total PADMM primal residual `r_primal`.
  
  The primal residual `r_primal` measures the convergence of the PADMM primal variables,
  w.r.t the consensus between the primal and slack variables. This reflects how well the
  solution satisfies the inequality constraints (joint-limits, contacts). Lower values
  require more iterations for higher accuracy.
  
  Range: [1e-10, inf)
  Units: dimensionless

#### newton:kamino:padmm:dualTolerance
  The tolerance on the total PADMM dual residual `r_dual`.
  
  The dual residual `r_dual` measures the convergence of the PADMM dual variables,
  and reflects the total violation over the set of constraints (joints, joint-limits,
  contacts). Lower values require more iterations for higher accuracy.
  
  Range: [1e-10, inf)
  Units: dimensionless

#### newton:kamino:padmm:complementarityTolerance
  The tolerance on the total PADMM complementarity residual `r_compl`.
  
  The complementarity residual `r_compl` measures how well the solution satisfies the
  complementarity conditions associated with inequality constraints (joint-limits,
  contacts). Lower values require more iterations for higher accuracy.
  
  Range: [1e-10, inf)
  Units: dimensionless

#### newton:kamino:padmm:warmstarting
  The warmstarting mode used for the PADMM constraint solver.
  
  Options:
  - "none": No warmstarting is performed.
  - "internal": Warmstart using the PADMM internal solver state from the previous time step.
  - "containers": Warmstart using cached per-constraint impulses and velocities from the previous time step.
  
  Default: "containers"

#### newton:kamino:padmm:useAcceleration
  Whether to use Nesterov acceleration in the PADMM constraint solver.
  
  When enabled, Nesterov acceleration is applied to the PADMM
  iterations to potentially improve the rate of convergence.

#### newton:kamino:constraints:usePreconditioning
  Whether to use problem preconditioning in the constraint forward dynamics.
  
  When enabled, the forward dynamics problem is scaled to improve numerical conditioning, which
  can lead to solver robustness for very ill-conditioned systems. It may however slow down
  convergence for well-conditioned systems.

#### newton:kamino:constraints:alpha
  Global default Baumgarte stabilization parameter for bilateral joint constraints.
  
  This parameter controls the amount of configuration-level error correction applied to bilateral
  joint constraints (e.g. hinge, ball-and-socket). Higher values increase stiffness and reduce
  positional drift, but may lead to instability if set too high.
  
  Range: [0.0, 1.0]
  Units: dimensionless

#### newton:kamino:constraints:beta
  Global default Baumgarte stabilization parameter for unilateral joint-limit constraints.
  
  This parameter controls the amount of configuration-level error correction applied to unilateral
  joint-limit constraints. Higher values increase stiffness and reduce positional drift, but may
  lead to instability if set too high.
  
  Range: [0.0, 1.0]
  Units: dimensionless

#### newton:kamino:constraints:gamma
  Global default Baumgarte stabilization parameter for unilateral contact constraints.
  
  This parameter controls the amount of configuration-level error correction applied to unilateral
  contact constraints. Higher values increase stiffness and reduce positional drift, but may
  lead to instability if set too high.
  
  Range: [0.0, 1.0]
  Units: dimensionless

#### newton:kamino:jointCorrection
  The rotation roll-over correction mode to use for rotational joint DoFs.
  
  Options:
  - "none": No joint coordinate correction is applied. Rotational joint coordinates are computed to lie within ``[-pi, pi]``.
  - "twopi": Rotational joint coordinates are computed to always lie within ``[-2*pi, 2*pi]``.
  - "continuous": Rotational joint coordinates are continuously accumulated and thus unbounded.
  This means that joint coordinates can increase/decrease indefinitely over time,
  but are limited to numerical precision limits (i.e. ``[-FLOAT32_MAX, FLOAT32_MAX]``).
  
  Default: "twopi"


### NewtonArticulationRootAPI
NewtonArticulationRootAPI extends the `PhysicsArticulationRootAPI` with additional attributes for Newton.

By applying this schema, the prim also inherits the `PhysicsArticulationRootAPI` schema.

#### newton:selfCollisionEnabled
  Whether self collisions should be enabled or disabled for the entire articulation.
  
  When disabled, this is equivalent to applying `PhysicsFilteredPairsAPI` relationships between all bodies in the articulation.


### NewtonCollisionAPI
NewtonCollisionAPI applies on top of a Gprim, providing extra collision attributes for Newton.

By applying this schema, the prim also inherits the `PhysicsCollisionAPI` schema.

#### newton:contactMargin
  Outward offset/inflation of the shape's surface for collision detection.
  
  Extends/inflates the effective collision surface outward by this amount. When two shapes collide,
  their contact margins are summed (`margin_a + margin_b`) to determine the total separation/penetration.
  
  Range: [0, inf)
  Units: distance

#### newton:contactGap
  Distance threshold below which contacts are detected.
  
  AABBs are expanded by this value and potential contact points get added into the solver
  once their separation is smaller than the contact gap sum (`gap_a + gap_b`).
  
  If `newton:contactGap` is set to `-inf`, the contact gap is assumed to match `newton:contactMargin`,
  ensuring collisions are not missed when inflated surfaces approach each other.
  
  Range: [-inf, inf)
  Units: distance


### NewtonMeshCollisionAPI
NewtonMeshCollisionAPI applies on top of a Mesh, providing extra mesh collision attributes for Newton.

By applying this schema, the prim also inherits the `PhysicsCollisionAPI`, `NewtonCollisionAPI` and `PhysicsMeshCollisionAPI` schemas.

#### newton:maxHullVertices
  Maximum number of vertices in the resulting convex hull approximation.
  
  This value is only relevant when `physics:approximation = "convexHull"`.
  
  If `newton:maxHullVertices` is set to -1, the hull computation should use as many vertices as necessary to produce a perfect convex hull.
  
  Range: [-1, inf)
  Units: dimensionless


### NewtonMaterialAPI
NewtonMaterialAPI applies on top of a Material, providing extra physical material attributes for Newton.

By applying this schema, the prim also inherits the `PhysicsMaterialAPI` schema.

#### newton:torsionalFriction
  Torsional friction coefficient (resistance to spinning at a contact point).
  
  Range: [0, inf)
  Units: dimensionless

#### newton:rollingFriction
  Rolling friction coefficient (resistance to rolling motion).
  
  Range: [0, inf)
  Units: dimensionless


### NewtonMimicAPI
NewtonMimicAPI applies on top of a PhysicsJoint, adding additional constraints to mimic the DOFs of another joint.

A mimic constraint enforces that `joint0 = coef0 + coef1 * joint1` for the joint DOFs,
where `joint0` is this joint (the follower) and `joint1` (the leader) is specified via the `newton:mimicJoint` relationship.

The behavior on multi-DOF joints is undefined. The mimic constraint will be applied to each DOF independently,
but as the coefficients are shared across all DOFs, the units for translational and rotational DOFs will be mixed.
Therefore, it is recommended to only use this API on single-DOF joints.

#### newton:mimicEnabled
  Whether the mimic constraint is active.
  
  When disabled, the follower joint moves independently, as though the mimic constraint was not applied.

#### newton:mimicCoef0
  Offset added after scaling the leader joint's position/angle.
  
  In the mimic equation which constrains the joint DOFs, `joint0 = coef0 + coef1 * joint1`,
  this is the constant offset term.
  
  Range: (-inf, inf)
  Units: distance or degrees (matches the joint type for single-DOF joints)

#### newton:mimicCoef1
  Scale factor applied to the leader joint's position/angle.
  
  In the mimic equation which constrains the joint DOFs, `joint0 = coef0 + coef1 * joint1`,
  this is the linear coefficient.
  
  A value of 1.0 means the follower tracks the leader exactly (plus offset from `newton:mimicCoef0`),
  while negative values reverse the direction.
  
  Range: (-inf, inf)
  Units: dimensionless

