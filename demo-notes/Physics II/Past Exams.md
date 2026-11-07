---
tags:
  - physics-ii
---
# Quick Links
- **Past Exams**:
	- [[#25 June 2026 Exam]]
		1. **Q1: Electrostatic force:** *compute* the force between two point charges separated by a known distance.
		2. **Q2: Magnetic field of a wire:** *compute* the field at a given distance using Ampere's law.
		3. **(10 pts)** **Electric field and potential:** *find* the field of a conducting sphere in all regions and its potential.
		4. **(10 pts)** **Electromagnetic induction:** *find* the induced electromotive force and current direction as a loop leaves a magnetic field.

# Memorize
- [[#^coulomb-law|Coulomb's law]]
- [[#^ampere-wire|Magnetic field around a long straight wire]]
- [[#^conducting-sphere-answer|Conducting sphere field and potential]]
- [[#^faraday-lenz|Faraday's and Lenz's laws]]

# Solve again
- [[#Exercise Q1|Electrostatic force]]
- [[#Exercise Q2|Magnetic field of a wire]]
- [[#Exercise Problem 1|Conducting sphere]]
- [[#Exercise Problem 2|Induction loop]]

# Past Exams
## 25 June 2026 Exam

### Exercise Q1
Q1. Two point charges q1 = 2 uC and q2 = -3 uC are 0.5 m apart. Find the force.

#### Solution
Coulomb's law gives the force between two point charges. The force acts along the line joining the charges. Opposite signs mean the force is attractive.

*Example:* Here, the charges are $2\,\mu\text{C}$ and $-3\,\mu\text{C}$, so they attract.

Convert the charges to coulombs and use the distance $r=0.5\,\text{m}$:

$$
F = k\frac{|q_1q_2|}{r^2}
$$

Here, $k \approx 8.99\times10^9\,\text{N}\,\text{m}^2/\text{C}^2$.

$$
\begin{aligned}
F &= (8.99\times10^9)\frac{|(2\times10^{-6})(-3\times10^{-6})|}{(0.5)^2} \\
  &= (8.99\times10^9)\frac{6\times10^{-12}}{0.25} \\
  &= 0.216\,\text{N}
\end{aligned}
$$

It is wrong to report only a positive scalar as the full force because the force has a direction. It points toward the other charge.

#### Final Answer
The force has magnitude $0.216\,\text{N}$ and is attractive: each charge is pulled toward the other. ^coulomb-law

### Exercise Q2
Q2. A long straight wire carries I = 5 A. Find B at 10 cm using Ampere's law.

#### Solution
Ampere's law relates the magnetic field around a closed path to the current enclosed. A long straight wire has circular symmetry, so the field has constant magnitude on a circle of radius $r$ centered on the wire.

*Example:* At radius $r=0.10\,\text{m}$, every point on this circle has the same field magnitude.

Ampere's law is

$$
\oint \mathbf{B}\cdot d\mathbf{l} = \mu_0 I_{\text{enc}}
$$

On a circle, $\mathbf{B}$ is parallel to $d\mathbf{l}$ and constant, so

$$
B(2\pi r)=\mu_0 I
$$

Rearrange and substitute $I=5\,\text{A}$ and $r=0.10\,\text{m}$:

$$
\begin{aligned}
B &= \frac{\mu_0 I}{2\pi r} \\
  &= \frac{(4\pi\times10^{-7})(5)}{2\pi(0.10)} \\
  &= 1.0\times10^{-5}\,\text{T}
\end{aligned}
$$

#### Final Answer
At $10\,\text{cm}$ from the wire, the magnetic field magnitude is $1.0\times10^{-5}\,\text{T}$. Its direction is tangent to circles centered on the wire, given by the right-hand rule. ^ampere-wire

### Exercise Problem 1 (10 pts)
Problem 1 (10 pts). A conducting sphere of radius R carries charge Q. Find E(r) everywhere using Gauss's law and the potential V(r).

#### Solution
A conductor in electrostatic equilibrium has zero electric field inside its material. Any excess charge lies on its surface. Spherical symmetry makes the field radial and equal in magnitude everywhere on a concentric spherical Gaussian surface.

*Example:* A Gaussian sphere with radius $r<R$ encloses no excess charge, so its field is zero.

##### 1. Find the electric field
Gauss's law states that electric flux through a closed surface equals enclosed charge divided by the permittivity of free space:

$$
\oint \mathbf{E}\cdot d\mathbf{A} = \frac{Q_{\text{enc}}}{\varepsilon_0}
$$

For $r<R$, the field inside the conductor is zero. For $r>R$, a concentric sphere encloses charge $Q$. Its area is $4\pi r^2$, and the field is radial:

$$
E(4\pi r^2)=\frac{Q}{\varepsilon_0}
$$

Thus the field is

$$
\mathbf{E}(r)=
\begin{cases}
0, & r<R \\
\frac{Q}{4\pi\varepsilon_0r^2}\hat{\mathbf{r}}, & r>R
\end{cases}
$$

At the surface, the field just outside is $\frac{Q}{4\pi\varepsilon_0R^2}\hat{\mathbf{r}}$; just inside it is zero.

##### 2. Find the potential
Electric potential is defined relative to a chosen reference. Choose $V(\infty)=0$. Outside the sphere, the field is the same as that of a point charge $Q$ at the center, so

$$
V(r)=\frac{Q}{4\pi\varepsilon_0r}, \qquad r\ge R
$$

Inside the conductor, the electric field is zero, so the potential is constant and equals its surface value:

$$
V(r)=\frac{Q}{4\pi\varepsilon_0R}, \qquad r\le R
$$

Common mistake: Setting the potential inside to zero because the electric field is zero. A zero field means constant potential, not necessarily zero potential.

#### Final Answer
With $V(\infty)=0$,

$$
\mathbf{E}(r)=
\begin{cases}
0, & r<R \\
\frac{Q}{4\pi\varepsilon_0r^2}\hat{\mathbf{r}}, & r>R
\end{cases}
\qquad
V(r)=
\begin{cases}
\frac{Q}{4\pi\varepsilon_0R}, & r\le R \\
\frac{Q}{4\pi\varepsilon_0r}, & r\ge R
\end{cases}
$$

The potential is continuous at $r=R$. ^conducting-sphere-answer

### Exercise Problem 2 (10 pts)
Problem 2 (10 pts). A rectangular loop moves out of a uniform magnetic field at speed v. Find the induced emf and current direction (Lenz).

#### Solution
Faraday's law says a changing magnetic flux induces an electromotive force (emf), meaning energy supplied per unit charge around the loop. Lenz's law gives the induced current direction: it produces a magnetic field that opposes the change in flux.

*Example:* As the loop leaves the field region, the flux through it decreases, so the induced field tries to maintain the original flux.

Let the magnetic field have magnitude $B$, the loop have width $w$ along its direction of motion, and the side perpendicular to the motion have length $\ell$. While part of the loop remains in the field, the overlap area decreases at rate $\ell v$. The magnetic flux magnitude is $\Phi_B=BA$, so

$$
|\mathcal{E}| = \left|\frac{d\Phi_B}{dt}\right|=B\ell v
$$

If the field points into the page, the decreasing inward flux induces an inward field. By the right-hand rule, the induced current is clockwise. If the field points out of the page, the current is counterclockwise.

The problem gives no numerical dimensions or field magnitude, so the emf is expressed in terms of $B$, $\ell$, and $v$.

#### Final Answer
While the loop is partly inside the uniform field, the induced emf magnitude is $B\ell v$, where $\ell$ is the loop side perpendicular to its motion. The current produces a magnetic field in the same direction as the original field to oppose the decreasing flux; it is clockwise for an into-the-page field and counterclockwise for an out-of-the-page field. ^faraday-lenz
FILE>>
