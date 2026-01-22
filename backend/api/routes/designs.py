"""
Ship Design API routes.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional, Any

from ...core.components import (
    ComponentLoader, get_component_loader, load_components,
    Component, ShipDesign, Hull
)
from ...core.game_objects.item import ItemType

router = APIRouter(prefix="/api/designs", tags=["designs"])


class HullModuleResponse(BaseModel):
    """Response model for hull module slot."""
    cell_number: int
    component_type: str
    component_maximum: int
    component_count: int = 0
    allocated_component: Optional[str] = None


class HullResponse(BaseModel):
    """Response model for hull data."""
    name: str
    mass: int
    fuel_capacity: int
    dock_capacity: int
    base_cargo: int
    armor_strength: int
    battle_initiative: int
    modules: List[HullModuleResponse]
    is_starbase: bool
    cost: Dict[str, int]


class EngineResponse(BaseModel):
    """Response model for engine data."""
    name: str
    mass: int
    fuel_consumption: List[int]
    ram_scoop: bool
    fastest_safe_speed: int
    optimal_speed: int
    free_warp_speed: int
    cost: Dict[str, int]


class ComponentResponse(BaseModel):
    """Response model for any component."""
    name: str
    item_type: str
    mass: int
    cost: Dict[str, int]
    description: str
    tech_requirements: Dict[str, int]
    properties: Dict[str, Any]


class ShipDesignResponse(BaseModel):
    """Response model for ship design."""
    name: str
    hull_name: str
    mass: int
    cost: Dict[str, int]
    armor: int
    shield: int
    fuel_capacity: int
    cargo_capacity: int
    is_starbase: bool
    can_colonize: bool
    has_weapons: bool


class DesignCreateRequest(BaseModel):
    """Request model for creating a design."""
    name: str
    hull_name: str
    modules: Dict[int, Dict[str, int]]  # cell_number -> {component_name: count}


def _ensure_components_loaded() -> ComponentLoader:
    """Ensure components are loaded."""
    loader = get_component_loader()
    if not loader.is_loaded:
        load_components("backend/data/components.xml")
    return loader


def _hull_to_response(comp: Component) -> HullResponse:
    """Convert hull component to response model."""
    hull_prop = comp.get_property("Hull")
    hull_data = hull_prop.values if hull_prop else {}

    modules = []
    for m in hull_data.get("modules", []):
        modules.append(HullModuleResponse(
            cell_number=m.get("cell_number", -1),
            component_type=m.get("component_type", ""),
            component_maximum=m.get("component_maximum", 1),
            component_count=m.get("component_count", 0),
            allocated_component=m.get("allocated_component")
        ))

    return HullResponse(
        name=comp.name,
        mass=comp.mass,
        fuel_capacity=hull_data.get("fuel_capacity", 0),
        dock_capacity=hull_data.get("dock_capacity", 0),
        base_cargo=hull_data.get("base_cargo", 0),
        armor_strength=hull_data.get("armor_strength", 0),
        battle_initiative=hull_data.get("battle_initiative", 0),
        modules=modules,
        is_starbase=hull_data.get("fuel_capacity", 0) == 0,
        cost={
            "ironium": comp.cost.ironium,
            "boranium": comp.cost.boranium,
            "germanium": comp.cost.germanium,
            "energy": comp.cost.energy
        }
    )


def _engine_to_response(comp: Component) -> EngineResponse:
    """Convert engine component to response model."""
    engine_prop = comp.get_property("Engine")
    engine_data = engine_prop.values if engine_prop else {}
    fuel = engine_data.get("fuel_consumption", [0] * 10)

    # Calculate free warp speed
    free_warp = 0
    for i in range(9, -1, -1):
        if fuel[i] == 0:
            free_warp = i + 1
            break

    return EngineResponse(
        name=comp.name,
        mass=comp.mass,
        fuel_consumption=fuel,
        ram_scoop=engine_data.get("ram_scoop", False),
        fastest_safe_speed=engine_data.get("fastest_safe_speed", 0),
        optimal_speed=engine_data.get("optimal_speed", 0),
        free_warp_speed=free_warp,
        cost={
            "ironium": comp.cost.ironium,
            "boranium": comp.cost.boranium,
            "germanium": comp.cost.germanium,
            "energy": comp.cost.energy
        }
    )


@router.get("/hulls", response_model=List[HullResponse])
async def list_hulls() -> List[HullResponse]:
    """List all available hull components."""
    loader = _ensure_components_loaded()
    hulls = loader.get_all_hulls()
    return [_hull_to_response(h) for h in hulls]


@router.get("/hulls/{hull_name}", response_model=HullResponse)
async def get_hull(hull_name: str) -> HullResponse:
    """Get a specific hull by name."""
    loader = _ensure_components_loaded()
    comp = loader.get_component(hull_name)
    if comp is None or comp.item_type not in [ItemType.HULL, ItemType.STARBASE]:
        raise HTTPException(status_code=404, detail="Hull not found")
    return _hull_to_response(comp)


@router.get("/engines", response_model=List[EngineResponse])
async def list_engines() -> List[EngineResponse]:
    """List all available engine components."""
    loader = _ensure_components_loaded()
    engines = loader.get_all_engines()
    return [_engine_to_response(e) for e in engines]


@router.get("/engines/{engine_name}", response_model=EngineResponse)
async def get_engine(engine_name: str) -> EngineResponse:
    """Get a specific engine by name."""
    loader = _ensure_components_loaded()
    comp = loader.get_component(engine_name)
    if comp is None or comp.item_type != ItemType.ENGINE:
        raise HTTPException(status_code=404, detail="Engine not found")
    return _engine_to_response(comp)


@router.get("/components", response_model=List[ComponentResponse])
async def list_components(item_type: Optional[str] = None) -> List[ComponentResponse]:
    """List all components, optionally filtered by type."""
    loader = _ensure_components_loaded()

    if item_type:
        try:
            it = ItemType[item_type.upper()]
            components = loader.get_components_by_type(it)
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Invalid item type: {item_type}")
    else:
        components = list(loader.components.values())

    results = []
    for comp in components:
        props = {}
        for prop_type, prop in comp.properties.items():
            props[prop_type] = prop.values

        results.append(ComponentResponse(
            name=comp.name,
            item_type=comp.item_type.name,
            mass=comp.mass,
            cost={
                "ironium": comp.cost.ironium,
                "boranium": comp.cost.boranium,
                "germanium": comp.cost.germanium,
                "energy": comp.cost.energy
            },
            description=comp.description,
            tech_requirements=comp.required_tech.levels,
            properties=props
        ))

    return results


@router.get("/components/{component_name}", response_model=ComponentResponse)
async def get_component(component_name: str) -> ComponentResponse:
    """Get a specific component by name."""
    loader = _ensure_components_loaded()
    comp = loader.get_component(component_name)
    if comp is None:
        raise HTTPException(status_code=404, detail="Component not found")

    props = {}
    for prop_type, prop in comp.properties.items():
        props[prop_type] = prop.values

    return ComponentResponse(
        name=comp.name,
        item_type=comp.item_type.name,
        mass=comp.mass,
        cost={
            "ironium": comp.cost.ironium,
            "boranium": comp.cost.boranium,
            "germanium": comp.cost.germanium,
            "energy": comp.cost.energy
        },
        description=comp.description,
        tech_requirements=comp.required_tech.levels,
        properties=props
    )


@router.get("/stats")
async def get_component_stats() -> Dict[str, int]:
    """Get component count statistics by type."""
    loader = _ensure_components_loaded()
    return loader.get_stats()
